---
id: 21708
severity: "High"
---

# An infinite loop in `MultiFeeDistribution.sol` withdraw`

## Description

An infinite loop will block the withdraw process.

## Proof of Concept

In the MultiFeeDistribution.sol the `withdraw` function will start going through user’s locked amounts if they do not have enough unlocked to cover their withdraw request:

```solidity
if (amount <= bal.unlocked) {
    bal.unlocked = bal.unlocked - amount;
} else {
    uint256 remaining = amount - bal.unlocked;
    if (bal.earned < remaining) revert InvalidEarned();
    bal.unlocked = 0;
    uint256 sumEarned = bal.earned;
    uint256 i;
    for (i = 0; ; ) {
        uint256 earnedAmount = _userEarnings[_address][i].amount;
        if (earnedAmount == 0) continue;
```

However, as you can see it will stay at 0 and the following check will execute:

```solidity
if (earnedAmount == 0) continue;
```

This continues and will start a new iteration of the loop; however, it will still be `0` and this loop will never end. As a result, claiming from locked amounts with penalty will not be possible.

## Recommendation

Rewrite the code the following way:

```solidity
if (earnedAmount == 0) {
    i++;
    continue;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an infinite loop in the withdraw function of MultiFeeDistribution.sol. The function iterates over a user's locked earnings using a for loop declared as for (i = 0; ; ). Inside the loop, when the amount to withdraw exceeds the unlocked balance, the code reads the next earned entry and checks if (earnedAmount == 0) continue;. Because the loop header does not include an increment of i, the continue statement jumps to the next iteration without advancing the index, leaving i unchanged. As a result, if an earned entry with amount zero is encountered, the condition remains true forever and the loop never terminates. This situation occurs when a user tries to withdraw more than their unlocked balance and the contract must consume locked earnings that are recorded as zero, which is a realistic state for many users. The infinite loop consumes all supplied gas, causing the transaction to run out of gas and revert, effectively denying service to the caller. From a user perspective the withdrawal transaction appears to be stuck, the UI shows a pending transaction, and the expected funds are never transferred, leaving the user's balance unchanged. The impact is a denial‑of‑service on withdrawals, preventing users from claiming locked amounts and potentially freezing protocol liquidity. The bug was discovered during a manual audit that examined the control flow of the withdraw routine. It is hard to notice because the Solidity compiler does not flag missing loop increments, and the code path is only exercised when specific conditions are met. The issue belongs to the class of unbounded loop or missing iterator increment bugs, which violate the assumption that a loop will eventually terminate after processing all entries. The correct fix is to ensure the loop index is incremented on each iteration, for example by adding i++ before the continue or by rewriting the loop with an explicit termination condition such as for (uint256 i = 0; i < _userEarnings[_address].length; i++). This change restores the expected behavior where the contract deducts earned amounts, updates balances, and completes the withdrawal.
