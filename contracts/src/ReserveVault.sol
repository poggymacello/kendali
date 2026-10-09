// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";

/// @title ReserveVault — ERC-4626 reserve where the treasury parks idle cash.
/// @notice A stand-in for a money-market / tokenized-deposit product. Yield is simulated
///         on testnets by transferring extra underlying into the vault.
contract ReserveVault is ERC4626 {
    constructor(IERC20 underlying) ERC20("Kendali Reserve tUSDC", "krUSDC") ERC4626(underlying) {}

    /// @dev Virtual-share offset hardens the vault against the ERC-4626 donation/inflation attack.
    function _decimalsOffset() internal pure override returns (uint8) {
        return 6;
    }
}
