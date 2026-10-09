// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {KendaliVault} from "../src/KendaliVault.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {ReserveVault} from "../src/ReserveVault.sol";

contract KendaliVaultTest is Test {
    MockUSDC usdc;
    ReserveVault reserve;
    KendaliVault vault;

    address owner = makeAddr("owner");
    address agent = makeAddr("agent");
    address supplier = makeAddr("supplier");
    address landlord = makeAddr("landlord");
    address attacker = makeAddr("attacker");

    uint256 constant USD = 1e6;
    uint64 constant POLICY_DELAY = 2 days;
    uint64 constant COOLDOWN = 1 days;
    uint64 constant TTL = 3 days;

    function setUp() public {
        vm.warp(1_790_000_000);
        usdc = new MockUSDC(address(this));
        reserve = new ReserveVault(usdc);
        vault = new KendaliVault(
            usdc,
            reserve,
            owner,
            agent,
            KendaliVault.Limits({autoLimit: uint128(500 * USD), dailyAutoLimit: uint128(1_000 * USD), hardCap: uint128(5_000 * USD)}),
            POLICY_DELAY,
            COOLDOWN,
            TTL
        );
        usdc.mint(address(vault), 20_000 * USD);
        vm.startPrank(owner);
        vault.addPayee(supplier, keccak256("PT Sumber Makmur"));
        vault.addPayee(landlord, keccak256("CV Ruko Sejahtera"));
        vm.stopPrank();
        vm.warp(block.timestamp + COOLDOWN + 1);
    }

    function _ref(string memory s) internal pure returns (bytes32) {
        return keccak256(bytes(s));
    }

    // ------------------------------------------------------------ happy paths
    function test_AgentPaysWithinLimits() public {
        vm.prank(agent);
        vault.pay(supplier, 300 * USD, _ref("INV-1"), _ref("decision-1"));
        assertEq(usdc.balanceOf(supplier), 300 * USD);
        assertEq(vault.remainingDailyAuto(), 700 * USD);
    }

    function test_MakerCheckerFlow() public {
        vm.prank(agent);
        uint256 id = vault.propose(landlord, 2_500 * USD, _ref("RENT-OCT"), _ref("d"));
        assertEq(usdc.balanceOf(landlord), 0);
        vm.prank(owner);
        vault.approveProposal(id);
        assertEq(usdc.balanceOf(landlord), 2_500 * USD);
        assertEq(uint8(vault.getProposal(id).status), uint8(KendaliVault.ProposalStatus.Executed));
    }

    function test_ReserveSweepAndWithdrawStayInCustody() public {
        vm.prank(agent);
        vault.sweepToReserve(10_000 * USD, _ref("sweep"));
        assertEq(vault.liquidBalance(), 10_000 * USD);
        assertApproxEqAbs(vault.reserveBalance(), 10_000 * USD, 1);
        vm.prank(agent);
        vault.withdrawFromReserve(4_000 * USD, _ref("withdraw"));
        assertEq(vault.liquidBalance(), 14_000 * USD);
        assertEq(usdc.balanceOf(agent), 0);
    }

    function test_DailyLimitResetsNextDay() public {
        vm.startPrank(agent);
        vault.pay(supplier, 500 * USD, _ref("a"), bytes32(0));
        vault.pay(supplier, 500 * USD, _ref("b"), bytes32(0));
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.ExceedsDailyLimit.selector, 1_001 * USD, 1_000 * USD));
        vault.pay(supplier, 1 * USD, _ref("c"), bytes32(0));
        vm.warp(block.timestamp + 1 days);
        vault.pay(supplier, 1 * USD, _ref("c"), bytes32(0));
        vm.stopPrank();
    }

    // ------------------------------------------------------------ compromised agent key
    function test_RevertWhen_AgentPaysNonAllowlisted() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.PayeeNotAllowed.selector, attacker));
        vault.pay(attacker, 1 * USD, _ref("x"), bytes32(0));
    }

    function test_RevertWhen_AgentExceedsAutoLimit() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.ExceedsAutoLimit.selector, 501 * USD, 500 * USD));
        vault.pay(supplier, 501 * USD, _ref("x"), bytes32(0));
    }

    function test_RevertWhen_DuplicateReference() public {
        vm.startPrank(agent);
        vault.pay(supplier, 100 * USD, _ref("INV-9"), bytes32(0));
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.RefAlreadyUsed.selector, _ref("INV-9")));
        vault.pay(supplier, 100 * USD, _ref("INV-9"), bytes32(0));
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.RefAlreadyUsed.selector, _ref("INV-9")));
        vault.propose(supplier, 100 * USD, _ref("INV-9"), bytes32(0));
        vm.stopPrank();
    }

    function test_RevertWhen_AgentTouchesPolicy() public {
        vm.startPrank(agent);
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.addPayee(attacker, bytes32(0));
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.scheduleLimits(KendaliVault.Limits(type(uint128).max, type(uint128).max, type(uint128).max));
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.setAgent(attacker);
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.ownerTransfer(attacker, 1);
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.unpause();
        vm.stopPrank();
    }

    function test_RevertWhen_AgentApprovesOwnProposal() public {
        vm.startPrank(agent);
        uint256 id = vault.propose(supplier, 3_000 * USD, _ref("big"), bytes32(0));
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.approveProposal(id);
        vm.stopPrank();
    }

    function test_RevertWhen_ProposalAboveHardCap() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.ExceedsHardCap.selector, 5_001 * USD, 5_000 * USD));
        vault.propose(supplier, 5_001 * USD, _ref("huge"), bytes32(0));
    }

    function test_NewPayeeCoolingOff() public {
        address newVendor = makeAddr("newVendor");
        vm.prank(owner);
        vault.addPayee(newVendor, bytes32(0));
        vm.prank(agent);
        vm.expectRevert();
        vault.pay(newVendor, 10 * USD, _ref("n1"), bytes32(0));
        // but a proposal (human approval) is allowed during cooling-off
        vm.prank(agent);
        uint256 id = vault.propose(newVendor, 10 * USD, _ref("n1"), bytes32(0));
        vm.prank(owner);
        vault.approveProposal(id);
        assertEq(usdc.balanceOf(newVendor), 10 * USD);
    }

    function test_PauseCircuitBreaker() public {
        vm.prank(agent);
        vault.pause();
        vm.prank(agent);
        vm.expectRevert(KendaliVault.IsPaused.selector);
        vault.pay(supplier, 1 * USD, _ref("p"), bytes32(0));
        // the agent cannot restart the vault
        vm.prank(agent);
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.unpause();
        // audit anchoring still works while paused
        vm.prank(agent);
        vault.commitDecision(_ref("blocked"), KendaliVault.DecisionKind.Blocked);
        vm.prank(owner);
        vault.unpause();
        vm.prank(agent);
        vault.pay(supplier, 1 * USD, _ref("p"), bytes32(0));
    }

    // ------------------------------------------------------------ governance
    function test_LooseningIsTimelockedTighteningIsImmediate() public {
        vm.startPrank(owner);
        vault.scheduleLimits(KendaliVault.Limits(uint128(100 * USD), uint128(200 * USD), uint128(1_000 * USD)));
        (uint128 a,,) = vault.limits();
        assertEq(a, 100 * USD);
        vault.scheduleLimits(KendaliVault.Limits(uint128(900 * USD), uint128(2_000 * USD), uint128(9_000 * USD)));
        (a,,) = vault.limits();
        assertEq(a, 100 * USD, "loosening must not apply immediately");
        vm.expectRevert();
        vault.applyLimits();
        vm.warp(block.timestamp + POLICY_DELAY);
        vault.applyLimits();
        (a,,) = vault.limits();
        assertEq(a, 900 * USD);
        vm.stopPrank();
    }

    function test_RejectReleasesReferenceAndExpiry() public {
        vm.prank(agent);
        uint256 id = vault.propose(supplier, 2_000 * USD, _ref("INV-R"), bytes32(0));
        vm.prank(owner);
        vault.rejectProposal(id, _ref("wrong amount"));
        assertFalse(vault.usedRef(_ref("INV-R")));
        vm.prank(agent);
        uint256 id2 = vault.propose(supplier, 1_900 * USD, _ref("INV-R"), bytes32(0));
        vm.warp(block.timestamp + TTL + 1);
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.ProposalIsExpired.selector, id2));
        vault.approveProposal(id2);
        vault.expireProposal(id2);
        assertEq(uint8(vault.getProposal(id2).status), uint8(KendaliVault.ProposalStatus.Expired));
    }

    function test_RemovedPayeeCannotBeApproved() public {
        vm.prank(agent);
        uint256 id = vault.propose(supplier, 2_000 * USD, _ref("INV-S"), bytes32(0));
        vm.prank(owner);
        vault.removePayee(supplier);
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(KendaliVault.PayeeNotAllowed.selector, supplier));
        vault.approveProposal(id);
    }

    function test_TwoStepOwnership() public {
        address newOwner = makeAddr("newOwner");
        vm.prank(owner);
        vault.transferOwnership(newOwner);
        assertEq(vault.owner(), owner);
        vm.prank(attacker);
        vm.expectRevert(KendaliVault.NotOwner.selector);
        vault.acceptOwnership();
        vm.prank(newOwner);
        vault.acceptOwnership();
        assertEq(vault.owner(), newOwner);
    }

    // ------------------------------------------------------------ fuzz
    function testFuzz_AgentNeverExceedsLimits(uint256 amount, uint8 payeeSel) public {
        address to = payeeSel % 3 == 0 ? supplier : (payeeSel % 3 == 1 ? landlord : attacker);
        amount = bound(amount, 1, 50_000 * USD);
        vm.prank(agent);
        try vault.pay(to, amount, keccak256(abi.encode(amount, payeeSel)), bytes32(0)) {
            assertTrue(to != attacker, "paid a non-allow-listed address");
            assertLe(amount, 500 * USD, "paid above autoLimit");
        } catch {}
        assertEq(usdc.balanceOf(attacker), 0);
    }
}

/// @dev Stateful fuzzing: an attacker who fully controls the agent key performs random
///      sequences of calls and time jumps. Invariants must hold after every call.
contract AgentKeyCompromiseHandler is Test {
    KendaliVault vault;
    MockUSDC usdc;
    address agent;
    address[] targets;
    uint256 public totalAutoPaid;
    uint256 nonce;

    constructor(KendaliVault v, MockUSDC u, address a, address[] memory t) {
        vault = v;
        usdc = u;
        agent = a;
        targets = t;
    }

    function pay(uint256 amount, uint256 sel) external {
        amount = bound(amount, 1, 10_000e6);
        address to = targets[sel % targets.length];
        vm.prank(agent);
        try vault.pay(to, amount, keccak256(abi.encode(nonce++)), bytes32(0)) {
            totalAutoPaid += amount;
        } catch {}
    }

    function propose(uint256 amount, uint256 sel) external {
        amount = bound(amount, 1, 10_000e6);
        vm.prank(agent);
        try vault.propose(targets[sel % targets.length], amount, keccak256(abi.encode(nonce++)), bytes32(0)) {} catch {}
    }

    function tryApprove(uint256 id) external {
        vm.prank(agent);
        try vault.approveProposal(id) {} catch {}
    }

    function tryGovernance(uint128 x) external {
        vm.startPrank(agent);
        try vault.addPayee(targets[targets.length - 1], bytes32(0)) {} catch {}
        try vault.scheduleLimits(KendaliVault.Limits(x, x, x)) {} catch {}
        try vault.ownerTransfer(targets[targets.length - 1], 1) {} catch {}
        vm.stopPrank();
    }

    function sweep(uint256 amount) external {
        amount = bound(amount, 1, 5_000e6);
        vm.prank(agent);
        try vault.sweepToReserve(amount, bytes32(0)) {} catch {}
    }

    function warp(uint256 secs) external {
        vm.warp(block.timestamp + bound(secs, 1, 2 days));
    }
}

contract KendaliVaultInvariantTest is Test {
    MockUSDC usdc;
    ReserveVault reserve;
    KendaliVault vault;
    AgentKeyCompromiseHandler handler;
    address owner = makeAddr("owner");
    address agent = makeAddr("agent");
    address supplier = makeAddr("supplier");
    address attacker = makeAddr("attacker");
    uint256 startDay;

    function setUp() public {
        vm.warp(1_790_000_000);
        usdc = new MockUSDC(address(this));
        reserve = new ReserveVault(usdc);
        vault = new KendaliVault(
            usdc, reserve, owner, agent, KendaliVault.Limits(uint128(500e6), uint128(1_000e6), uint128(5_000e6)), 2 days, 1 days, 3 days
        );
        usdc.mint(address(vault), 1_000_000e6);
        vm.prank(owner);
        vault.addPayee(supplier, bytes32(0));
        vm.warp(block.timestamp + 1 days + 1);
        startDay = block.timestamp / 1 days;
        address[] memory t = new address[](2);
        t[0] = supplier;
        t[1] = attacker;
        handler = new AgentKeyCompromiseHandler(vault, usdc, agent, t);
        targetContract(address(handler));
    }

    /// The attacker address (never allow-listed) can never receive funds.
    function invariant_AttackerNeverPaid() public view {
        assertEq(usdc.balanceOf(attacker), 0);
    }

    /// Agent-alone outflow can never exceed dailyAutoLimit per elapsed day.
    function invariant_AutoOutflowBoundedByDailyLimit() public view {
        uint256 daysElapsed = block.timestamp / 1 days - startDay + 1;
        assertLe(handler.totalAutoPaid(), daysElapsed * 1_000e6);
        assertEq(usdc.balanceOf(supplier), handler.totalAutoPaid());
    }

    /// The agent can never change the policy or the owner.
    function invariant_GovernanceUnchanged() public view {
        (uint128 a, uint128 d, uint128 h) = vault.limits();
        assertEq(a, 500e6);
        assertEq(d, 1_000e6);
        assertEq(h, 5_000e6);
        assertEq(vault.owner(), owner);
        assertEq(vault.agent(), agent);
    }

    /// Treasury value is conserved except for legitimate payments (custody never leaks).
    function invariant_TreasuryConserved() public view {
        assertApproxEqAbs(vault.totalTreasury() + usdc.balanceOf(supplier), 1_000_000e6, 10);
    }
}
