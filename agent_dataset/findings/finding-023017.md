---
id: 23017
severity: "High"
---

# VouchFaucet can be immediately drained by

## Description

The claimTokens function in the VouchFaucet contract fails to properly enforce the maxClaimable limit because it does not update the value in the claimedTokens mapping. This allows any address to claim an arbitrary amount of any token, potentially draining the entire token balance of the contract, in a single transaction or through multiple transactions.
Included below is the relevant code from the VouchFaucet followed by key insights:
```solidity
/// @notice Token address to msg sender to claimed amount
mapping(address => mapping(address => uint256)) public claimedTokens;
/// @notice Token address to max claimable amount
mapping(address => uint256) public maxClaimable;
/// @notice Claim tokens from this contract
function claimTokens(address token, uint256 amount) external {
    require(claimedTokens[token][msg.sender] <= maxClaimable[token], "amount>max");

    IERC20(token).transfer(msg.sender, amount);
    emit TokensClaimed(msg.sender, token, amount);
}
/// @notice Transfer ERC20 tokens
function transferERC20(address token, address to, uint256 amount) external onlyOwner {

    IERC20(token).transfer(to, amount);
}
```
• The claimedTokens mapping is never updated. It will always return 0 when looking up how much of any token has been claimed by any address.
• The maxClaimable mapping will by default return 0 for any token the contract could ever receive. The contract owner can use the setMaxClaimable function but is only able to set the claimable amount for any token to 0 or greater.
• The transferERC20 function is protected by the onlyOwner modifier signaling the desire to restrict access to this type of transfer.
• Currently no matter what the admin does the require statement in claimTokens will always pass because it evaluates an expression that will always effectively be: require(0 <= [uint256], "amount>max"); This makes claimTokens effectively equivalent to an unrestricted version of transferERC20.
Without the intended enforcement provided by the require statement the claimTokens function provides unrestricted external access to an ERC20 transfer function. This is clearly not intended as demonstrated by the presence of the onlyOwner on the similar transferERC20 function. The result is that any caller can immediately transfer out any amount of any token.
This oversight completely undermines the token distribution model of the faucet. If deployed without modification it would render the contract useless for the intended purpose due to its inability to securely hold any amount of any token.

## Proof of Concept

The proof of concept below imports and utilizes the protcols own TestWrapper for simplicity in setting up a realistic testing environment.
The test case demonstrates that despite the VouchFaucet containing mechanisms that clearly intend to disallow the faucet from being easily drained by a single address, such an outcome is possible with no effort.
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.16;
import {Test, console} from "forge-std/Test.sol";
import {TestWrapper} from "../TestWrapper.sol";
import {VouchFaucet} from "../../src/contracts/peripheral/VouchFaucet.sol";
import {IERC20} from "@openzeppelin/token/ERC20/IERC20.sol";
contract TestVouchFaucet is TestWrapper {
    VouchFaucet public vouchFaucet;
    uint256 public TRUST_AMOUNT = 10 * UNIT;

    function setUp() public {
        deployMocks();
        vouchFaucet = new VouchFaucet(address(userManagerMock), TRUST_AMOUNT);
    }

    function testDrainVouchFaucet() public {
        address bob = address(1234);
        erc20Mock.mint(address(vouchFaucet), 3 * UNIT);
        vouchFaucet.setMaxClaimable(address(erc20Mock), 1 * UNIT);
        assertEq(vouchFaucet.maxClaimable(address(erc20Mock)), 1 * UNIT);
        // Bob can claim any number of tokens despite maxClaimable set to 1 Unit
        vm.prank(bob);
        vouchFaucet.claimTokens(address(erc20Mock), 3 * UNIT);
        assertEq(IERC20(erc20Mock).balanceOf(bob), 3 * UNIT);
    }
}
```

## Recommendation

The following correction ensures that any individual address can't claim more than the set claimable amount, maintaining the intended token distribution model of the faucet.
File: VouchFaucet.sol
```solidity
function claimTokens(address token, uint256 amount) external {
    - require(claimedTokens[token][msg.sender] <= maxClaimable[token], "amount>max");
    ,!
    + uint256 newTotal = claimedTokens[token][msg.sender] + amount;
    + require(newTotal <= maxClaimable[token], "Exceeds max claimable amount");
    ,!
    + claimedTokens[token][msg.sender] = newTotal;
    IERC20(token).transfer(msg.sender, amount);
    emit TokensClaimed(msg.sender, token, amount);
}
```
The following additional recommendations should be considered. The suggestions won't impact legitimate users, but raise the effort required for an malicious actor to disrupt the intended functioning of the contract.
1. Ensure the claimedTokens mapping is updated before the transfer to avoid reentrancy risk, OpenZeppelin ReentrancyGuard could also be considered.
2. Consider adding an admin adjustable global cap on total tokens that can be claimed across all addresses to help control faucet outflows.
3. Consider implementing a time-based cooldown mechanism to limit the frequency of claims per address.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked token claim in the faucet contract that allows any address to withdraw an arbitrary amount of any ERC20 token. The root cause is that the claimTokens function checks the amount already claimed against a per‑token maximum but never updates the claimedTokens mapping after a successful claim. Because the mapping always returns zero, the require statement effectively becomes require(0 <= maxClaimable), which is always true regardless of the amount requested. An attacker can therefore call claimTokens with a large amount, receive the tokens via the ERC20 transfer, and repeat the call until the contract balance is exhausted. This can happen in a single transaction or across multiple transactions and does not depend on any special privileges; any external account can invoke the function. The impact is that the faucet’s token reserves disappear, breaking the intended distribution model and leaving legitimate users unable to obtain the limited amount they expect. Users would see the contract balance drop to zero, their own claim succeed with far more tokens than allowed, or conversely, the contract may appear empty when they try to claim. The issue was discovered during a security audit when the test suite demonstrated that setting a max claimable amount of one token unit still allowed a caller to claim three units. The bug is hard to notice because the require statement appears to enforce a limit, giving a false sense of safety, while the missing state update silently defeats the check. To fix the problem the contract must record the new total claimed amount before transferring tokens and verify that this new total does not exceed the configured maximum. Adding a re‑entrancy guard, a global cap, or a cooldown period can further harden the faucet against abuse. In generic terms the flaw belongs to the class of accounting or state‑inconsistency bugs where a critical invariant is not maintained due to an omitted state mutation, leading to unrestricted asset transfer.
