// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IERC4626} from "@openzeppelin/contracts/interfaces/IERC4626.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title KendaliVault — the on-chain guardrail layer of the Kendali AI treasury agent.
/// @notice The AI agent holds only the `agent` key. Whatever happens off-chain (prompt injection,
///         model error, compromised server), the agent key can ONLY:
///           * pay an allow-listed payee whose cooling-off period has passed,
///           * up to `autoLimit` per payment and `dailyAutoLimit` per UTC day,
///           * once per payment reference (duplicate-invoice protection),
///           * propose larger payments, which only the `owner` can approve (maker-checker),
///           * move cash between this vault and the ERC-4626 reserve (funds never leave custody),
///           * pause the vault (circuit breaker) and anchor decision hashes for audit.
///         It can never add payees, change limits, approve its own proposals or unpause.
///         Loosening a limit is time-locked; tightening is immediate.
contract KendaliVault is ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ------------------------------------------------------------------ types
    enum ProposalStatus {
        None,
        Pending,
        Executed,
        Rejected,
        Expired
    }

    /// @dev Kinds used when anchoring decisions that did not move funds.
    enum DecisionKind {
        Blocked,
        Held,
        Escalated,
        Info
    }

    struct Limits {
        uint128 autoLimit; // max single payment the agent may execute alone
        uint128 dailyAutoLimit; // max sum of agent-alone payments per UTC day
        uint128 hardCap; // max single payment even with owner approval
    }

    struct Payee {
        bool allowed;
        uint64 activeFrom; // agent may auto-pay only after this timestamp
        bytes32 metaHash; // hash of KYB record kept off-chain (legal name, registration no.)
    }

    struct Proposal {
        address to;
        uint128 amount;
        uint64 createdAt;
        ProposalStatus status;
        bytes32 ref;
        bytes32 decisionHash;
    }

    // ------------------------------------------------------------------ storage
    IERC20 public immutable asset;
    IERC4626 public immutable reserve;
    uint64 public immutable policyDelay;
    uint64 public immutable payeeCooldown;
    uint64 public immutable proposalTtl;

    address public owner;
    address public pendingOwner;
    address public agent;
    bool public paused;

    Limits public limits;
    Limits public pendingLimits;
    uint64 public pendingLimitsEta;

    mapping(address => Payee) public payees;
    mapping(bytes32 => bool) public usedRef;
    mapping(uint256 => uint256) public autoSpentOnDay;
    Proposal[] internal _proposals;

    // ------------------------------------------------------------------ events
    event AutoPaid(address indexed to, uint256 amount, bytes32 indexed ref, bytes32 decisionHash);
    event ProposalCreated(uint256 indexed id, address indexed to, uint256 amount, bytes32 indexed ref, bytes32 decisionHash);
    event ProposalApproved(uint256 indexed id, address indexed approver, address to, uint256 amount, bytes32 decisionHash);
    event ProposalRejected(uint256 indexed id, address indexed by, bytes32 reasonHash);
    event ProposalExpiredEvent(uint256 indexed id);
    event DecisionCommitted(bytes32 indexed decisionHash, DecisionKind kind);
    event ReserveDeposited(uint256 assets, uint256 shares, bytes32 decisionHash);
    event ReserveWithdrawn(uint256 assets, uint256 shares, bytes32 decisionHash);
    event PayeeAdded(address indexed payee, uint64 activeFrom, bytes32 metaHash);
    event PayeeRemoved(address indexed payee);
    event LimitsScheduled(uint128 autoLimit, uint128 dailyAutoLimit, uint128 hardCap, uint64 eta);
    event LimitsUpdated(uint128 autoLimit, uint128 dailyAutoLimit, uint128 hardCap);
    event PendingLimitsCancelled();
    event AgentChanged(address indexed previousAgent, address indexed newAgent);
    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Paused(address indexed by);
    event Unpaused(address indexed by);
    event OwnerTransfer(address indexed to, uint256 amount);

    // ------------------------------------------------------------------ errors
    error NotOwner();
    error NotAgent();
    error NotAgentOrOwner();
    error IsPaused();
    error ZeroAddress();
    error ZeroAmount();
    error InvalidRef();
    error InvalidLimits();
    error PayeeNotAllowed(address payee);
    error PayeeCoolingDown(address payee, uint64 activeFrom);
    error ExceedsAutoLimit(uint256 amount, uint256 autoLimit);
    error ExceedsDailyLimit(uint256 wouldSpend, uint256 dailyAutoLimit);
    error ExceedsHardCap(uint256 amount, uint256 hardCap);
    error RefAlreadyUsed(bytes32 ref);
    error ProposalNotPending(uint256 id);
    error ProposalIsExpired(uint256 id);
    error ProposalNotExpired(uint256 id);
    error NoPendingLimits();
    error TimelockNotReady(uint64 eta);
    error AssetMismatch();

    // ------------------------------------------------------------------ modifiers
    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyAgent() {
        if (msg.sender != agent) revert NotAgent();
        _;
    }

    modifier onlyAgentOrOwner() {
        if (msg.sender != agent && msg.sender != owner) revert NotAgentOrOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert IsPaused();
        _;
    }

    // ------------------------------------------------------------------ constructor
    constructor(
        IERC20 asset_,
        IERC4626 reserve_,
        address owner_,
        address agent_,
        Limits memory limits_,
        uint64 policyDelay_,
        uint64 payeeCooldown_,
        uint64 proposalTtl_
    ) {
        if (address(asset_) == address(0) || address(reserve_) == address(0)) revert ZeroAddress();
        if (owner_ == address(0) || agent_ == address(0)) revert ZeroAddress();
        if (reserve_.asset() != address(asset_)) revert AssetMismatch();
        _validateLimits(limits_);
        asset = asset_;
        reserve = reserve_;
        owner = owner_;
        agent = agent_;
        limits = limits_;
        policyDelay = policyDelay_;
        payeeCooldown = payeeCooldown_;
        proposalTtl = proposalTtl_;
        emit OwnershipTransferred(address(0), owner_);
        emit AgentChanged(address(0), agent_);
        emit LimitsUpdated(limits_.autoLimit, limits_.dailyAutoLimit, limits_.hardCap);
    }

    // ================================================================== AGENT
    /// @notice Agent-alone payment within the auto limits to an active, allow-listed payee.
    function pay(address to, uint256 amount, bytes32 ref, bytes32 decisionHash)
        external
        onlyAgent
        whenNotPaused
        nonReentrant
    {
        if (amount == 0) revert ZeroAmount();
        if (ref == bytes32(0)) revert InvalidRef();
        Payee memory p = payees[to];
        if (!p.allowed) revert PayeeNotAllowed(to);
        if (block.timestamp < p.activeFrom) revert PayeeCoolingDown(to, p.activeFrom);
        if (amount > limits.autoLimit) revert ExceedsAutoLimit(amount, limits.autoLimit);
        uint256 day = block.timestamp / 1 days;
        uint256 wouldSpend = autoSpentOnDay[day] + amount;
        if (wouldSpend > limits.dailyAutoLimit) revert ExceedsDailyLimit(wouldSpend, limits.dailyAutoLimit);
        if (usedRef[ref]) revert RefAlreadyUsed(ref);

        usedRef[ref] = true;
        autoSpentOnDay[day] = wouldSpend;
        asset.safeTransfer(to, amount);
        emit AutoPaid(to, amount, ref, decisionHash);
    }

    /// @notice Agent proposes a payment that needs the owner's approval (maker-checker).
    function propose(address to, uint256 amount, bytes32 ref, bytes32 decisionHash)
        external
        onlyAgent
        whenNotPaused
        returns (uint256 id)
    {
        if (amount == 0) revert ZeroAmount();
        if (ref == bytes32(0)) revert InvalidRef();
        if (!payees[to].allowed) revert PayeeNotAllowed(to);
        if (amount > limits.hardCap) revert ExceedsHardCap(amount, limits.hardCap);
        if (usedRef[ref]) revert RefAlreadyUsed(ref);

        usedRef[ref] = true;
        id = _proposals.length;
        _proposals.push(
            Proposal({
                to: to,
                amount: uint128(amount),
                createdAt: uint64(block.timestamp),
                status: ProposalStatus.Pending,
                ref: ref,
                decisionHash: decisionHash
            })
        );
        emit ProposalCreated(id, to, amount, ref, decisionHash);
    }

    /// @notice Park idle cash in the reserve. Funds stay in the vault's custody (shares held here).
    function sweepToReserve(uint256 assets, bytes32 decisionHash)
        external
        onlyAgent
        whenNotPaused
        nonReentrant
        returns (uint256 shares)
    {
        if (assets == 0) revert ZeroAmount();
        asset.forceApprove(address(reserve), assets);
        shares = reserve.deposit(assets, address(this));
        emit ReserveDeposited(assets, shares, decisionHash);
    }

    /// @notice Bring cash back from the reserve into the vault (never to any other address).
    function withdrawFromReserve(uint256 assets, bytes32 decisionHash)
        external
        onlyAgentOrOwner
        whenNotPaused
        nonReentrant
        returns (uint256 shares)
    {
        if (assets == 0) revert ZeroAmount();
        shares = reserve.withdraw(assets, address(this), address(this));
        emit ReserveWithdrawn(assets, shares, decisionHash);
    }

    /// @notice Anchor the hash of a decision that moved no funds (blocked, held, escalated).
    /// @dev Allowed while paused so the audit trail stays complete.
    function commitDecision(bytes32 decisionHash, DecisionKind kind) external onlyAgent {
        emit DecisionCommitted(decisionHash, kind);
    }

    // ================================================================== OWNER OR AGENT
    /// @notice Circuit breaker. The agent may stop the vault but only the owner may restart it.
    function pause() external onlyAgentOrOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    // ================================================================== OWNER
    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function approveProposal(uint256 id) external onlyOwner whenNotPaused nonReentrant {
        Proposal storage pr = _proposals[id];
        if (pr.status != ProposalStatus.Pending) revert ProposalNotPending(id);
        if (block.timestamp > uint256(pr.createdAt) + proposalTtl) revert ProposalIsExpired(id);
        if (!payees[pr.to].allowed) revert PayeeNotAllowed(pr.to);
        if (pr.amount > limits.hardCap) revert ExceedsHardCap(pr.amount, limits.hardCap);

        pr.status = ProposalStatus.Executed;
        asset.safeTransfer(pr.to, pr.amount);
        emit ProposalApproved(id, msg.sender, pr.to, pr.amount, pr.decisionHash);
    }

    function rejectProposal(uint256 id, bytes32 reasonHash) external onlyOwner {
        Proposal storage pr = _proposals[id];
        if (pr.status != ProposalStatus.Pending) revert ProposalNotPending(id);
        pr.status = ProposalStatus.Rejected;
        usedRef[pr.ref] = false; // a corrected invoice may be proposed again
        emit ProposalRejected(id, msg.sender, reasonHash);
    }

    /// @notice Anyone may mark a stale proposal as expired, releasing its reference.
    function expireProposal(uint256 id) external {
        Proposal storage pr = _proposals[id];
        if (pr.status != ProposalStatus.Pending) revert ProposalNotPending(id);
        if (block.timestamp <= uint256(pr.createdAt) + proposalTtl) revert ProposalNotExpired(id);
        pr.status = ProposalStatus.Expired;
        usedRef[pr.ref] = false;
        emit ProposalExpiredEvent(id);
    }

    /// @notice New payees enter a cooling-off period before the agent can pay them alone.
    function addPayee(address payee, bytes32 metaHash) external onlyOwner {
        if (payee == address(0)) revert ZeroAddress();
        uint64 activeFrom = uint64(block.timestamp) + payeeCooldown;
        payees[payee] = Payee({allowed: true, activeFrom: activeFrom, metaHash: metaHash});
        emit PayeeAdded(payee, activeFrom, metaHash);
    }

    function removePayee(address payee) external onlyOwner {
        delete payees[payee];
        emit PayeeRemoved(payee);
    }

    /// @notice Tightening takes effect immediately; any loosening waits `policyDelay`.
    function scheduleLimits(Limits calldata newLimits) external onlyOwner {
        _validateLimits(newLimits);
        Limits memory cur = limits;
        bool tightening = newLimits.autoLimit <= cur.autoLimit && newLimits.dailyAutoLimit <= cur.dailyAutoLimit
            && newLimits.hardCap <= cur.hardCap;
        if (tightening) {
            limits = newLimits;
            delete pendingLimits;
            pendingLimitsEta = 0;
            emit LimitsUpdated(newLimits.autoLimit, newLimits.dailyAutoLimit, newLimits.hardCap);
        } else {
            pendingLimits = newLimits;
            pendingLimitsEta = uint64(block.timestamp) + policyDelay;
            emit LimitsScheduled(newLimits.autoLimit, newLimits.dailyAutoLimit, newLimits.hardCap, pendingLimitsEta);
        }
    }

    /// @notice Anyone may apply scheduled limits once the timelock has elapsed.
    function applyLimits() external {
        if (pendingLimitsEta == 0) revert NoPendingLimits();
        if (block.timestamp < pendingLimitsEta) revert TimelockNotReady(pendingLimitsEta);
        Limits memory nl = pendingLimits;
        limits = nl;
        delete pendingLimits;
        pendingLimitsEta = 0;
        emit LimitsUpdated(nl.autoLimit, nl.dailyAutoLimit, nl.hardCap);
    }

    function cancelPendingLimits() external onlyOwner {
        if (pendingLimitsEta == 0) revert NoPendingLimits();
        delete pendingLimits;
        pendingLimitsEta = 0;
        emit PendingLimitsCancelled();
    }

    /// @notice Rotate or revoke (set to a burn address) the agent key immediately.
    function setAgent(address newAgent) external onlyOwner {
        if (newAgent == address(0)) revert ZeroAddress();
        emit AgentChanged(agent, newAgent);
        agent = newAgent;
    }

    /// @notice The business owner keeps ultimate control of its own funds.
    function ownerTransfer(address to, uint256 amount) external onlyOwner nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        asset.safeTransfer(to, amount);
        emit OwnerTransfer(to, amount);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert NotOwner();
        emit OwnershipTransferred(owner, pendingOwner);
        owner = pendingOwner;
        pendingOwner = address(0);
    }

    // ================================================================== VIEWS
    function proposalCount() external view returns (uint256) {
        return _proposals.length;
    }

    function getProposal(uint256 id) external view returns (Proposal memory) {
        return _proposals[id];
    }

    function liquidBalance() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function reserveBalance() public view returns (uint256) {
        return reserve.convertToAssets(reserve.balanceOf(address(this)));
    }

    function totalTreasury() external view returns (uint256) {
        return liquidBalance() + reserveBalance();
    }

    function remainingDailyAuto() external view returns (uint256) {
        uint256 spent = autoSpentOnDay[block.timestamp / 1 days];
        return spent >= limits.dailyAutoLimit ? 0 : limits.dailyAutoLimit - spent;
    }

    function isPayeeActive(address payee) external view returns (bool) {
        Payee memory p = payees[payee];
        return p.allowed && block.timestamp >= p.activeFrom;
    }

    // ================================================================== INTERNAL
    function _validateLimits(Limits memory l) internal pure {
        if (l.hardCap == 0 || l.autoLimit > l.hardCap || l.autoLimit > l.dailyAutoLimit) revert InvalidLimits();
    }
}
