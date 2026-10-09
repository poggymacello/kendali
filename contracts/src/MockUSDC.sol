// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title MockUSDC — 6-decimal test stablecoin used on local devnets and public testnets.
/// @notice Has no value. Only the deployer can mint. Production would settle in a regulated
///         instrument (tokenized deposit, licensed stablecoin or CBDC) instead.
contract MockUSDC is ERC20, Ownable {
    constructor(address initialOwner) ERC20("Kendali Test USD", "tUSDC") Ownable(initialOwner) {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
