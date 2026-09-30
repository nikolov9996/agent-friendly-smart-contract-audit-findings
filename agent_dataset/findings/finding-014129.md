---
id: 14129
severity: "High"
---

# H-1 checkpoint() resets totalEffectiveSupply

## Description

When ResolvStaking.checkpoint() is called with the zero address as the user, the variable totalEffectiveSupply is reset to zero because the function ResolvStakingCheckpoints.updateEffectiveBalance() returns zero for the zero address.
```solidity
• ResolvStakingCheckpoints.sol#L128
```
A hacker can pass the zero address to the checkpoint() function via ResolvStaking.updateCheckpoint(). Resetting totalEffectiveSupply to zero would prevent users from being able to withdraw funds from the contract due to an underflow at the following line:
```solidity
newTotalEffectiveSupply =
// (
_params.totalEffectiveSupply // =0
- oldEffectiveBalance // >0
// )
+ newEffectiveBalance;
```
ResolvStakingCheckpoints.sol#L163

## Proof of Concept

no poc

## Recommendation

1. In ResolvStakingCheckpoints.updateEffectiveBalance(), return the current totalEffectiveSupply when the user address is zero.
2. Change the order of operations when calculating newTotalEffectiveSupply, adding first, subtracting last:
```solidity
newTotalEffectiveSupply =
(_params.totalEffectiveSupply +
newEffectiveBalance)
- oldEffectiveBalance;
```
Client's Commentary:
56f2fe95
2.3 Medium
Not Found
2.4 Low

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic error in the staking contract that allows the total effective supply of staked tokens to be unintentionally reset to zero when the checkpoint function is invoked with the zero address. The root cause is that the internal helper that updates an account's effective balance returns a zero balance for the zero address, and the calling code uses this returned value directly to recompute the global totalEffectiveSupply without protecting against the special case. An attacker can trigger this condition by calling the public updateCheckpoint function and passing address(0) as the user argument. When the function processes the zero address, it calculates a new totalEffectiveSupply by subtracting the previous effective balance of a legitimate user from a total that has just been set to zero, which creates a negative intermediate value that underflows in unsigned arithmetic. The underflow causes the contract’s accounting state to become inconsistent, effectively preventing any subsequent withdrawal because the contract believes there is no effective supply to distribute. From a user’s perspective the symptom is that attempts to withdraw or claim rewards silently fail or revert, and the UI may show a staked balance of zero even though the user never unstaked. The issue occurs only when the checkpoint routine is called with the zero address, a situation that is not prevented by access controls and can be triggered by any external caller. It was discovered during a manual security audit when the auditors examined the checkpoint logic and noticed that the zero‑address path returned a zero balance, leading to an unexpected reset of the global supply variable. The bug is subtle because the zero address is a valid Solidity value and the function does not explicitly reject it, so the faulty state change can go unnoticed until a withdrawal is attempted. Conceptually, the fix is to treat the zero address as a no‑op in the balance‑update routine, returning the existing totalEffectiveSupply unchanged, and to reorder the arithmetic so that the new balance is added before the old balance is subtracted, thereby avoiding a temporary negative value. This class of bug falls under improper handling of sentinel values and arithmetic underflow in accounting‑critical smart contracts, violating the fundamental assumption that the total effective supply never becomes negative and that withdrawals are always backed by sufficient supply.
