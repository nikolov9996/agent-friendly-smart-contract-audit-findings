---
id: 18572
severity: "High"
---

# `withdrawProtocolFees`

## Description

The function `claimReward()` will take all of the rewards if the `amountRequested` it’s passed in is 0, which may result in the user’s rewards being lost.

## Proof of Concept

In `BoostAggregator.withdrawProtocolFees()`, the owner can take the `protocolRewards`.

The code is as follows:
```solidity
    function withdrawProtocolFees(address to) external onlyOwner {
        uniswapV3Staker.claimReward(to, protocolRewards);
        delete protocolRewards;
    }
```
From the above code, we can see that `uniswapV3Staker` is called to fetch and then clears `protocolRewards`.

Let’s look at the implementation of `uniswapV3Staker.claimReward()`:
```solidity
    contract UniswapV3Staker is IUniswapV3Staker, Multicallable {
    ....
        function claimReward(address to, uint256 amountRequested) external returns (uint256 reward) {
            reward = rewards[msg.sender];
            if (amountRequested != 0 && amountRequested < reward) {
                reward = amountRequested;
                rewards[msg.sender] -= reward;
            } else {
                rewards[msg.sender] = 0;
            }

            if (reward > 0) hermes.safeTransfer(to, reward);

            emit RewardClaimed(to, reward);
        }
```
The current implementation is if the `amountRequested==0` passed, it means that all `rewards[msg.sender]` of this `msg.sender` are taken.

This leads to the following problems:

1. If a malicious `owner` calls `withdrawProtocolFees()` twice in a row, it will take all of the `rewards` in the `BoostAggregator`.
2. Also, you probably didn’t realize that `withdrawProtocolFees()` was called when `protocolRewards==0`.

As a result, the rewards that belong to users in `BoostAggregator` are lost.

## Recommendation

Modify `claimReward()` to remove `amountRequested != 0`:
```solidity
    contract UniswapV3Staker is IUniswapV3Staker, Multicallable {
    ....
        function claimReward(address to, uint256 amountRequested) external returns (uint256 reward) {
            reward = rewards[msg.sender];
            if (amountRequested < reward) {
                reward = amountRequested;
                rewards[msg.sender] -= reward;
            } else {
                rewards[msg.sender] = 0;
            }

            if (reward > 0) hermes.safeTransfer(to, reward);

            emit RewardClaimed(to, reward);
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the reward‑claiming function of the UniswapV3Staker contract. The function accepts an amountRequested parameter and contains a conditional check that treats a zero value as a special case: if amountRequested is zero the function skips the amount comparison and proceeds to set the caller’s entire reward balance to zero, effectively transferring the full amount to the supplied destination address. This logic is exposed through the BoostAggregator.withdrawProtocolFees method, which is restricted to the contract owner. The owner can invoke withdrawProtocolFees with the protocolRewards variable, which may be zero. When protocolRewards equals zero, the call to claimReward passes a zero amountRequested, triggering the “withdraw all” branch. Consequently, the owner can drain all rewards that are recorded for the BoostAggregator address, including rewards that belong to individual users of the protocol. The exploit can be performed repeatedly; a malicious owner can call withdrawProtocolFees multiple times, each time causing the contract to transfer any remaining reward balance to an address of the owner’s choosing. The impact is the loss of user‑earned rewards, effectively disappearing funds from user balances and breaking the accounting guarantees of the staking system. The issue manifests whenever the owner calls withdrawProtocolFees, especially when the protocolRewards counter is zero or uninitialized, a situation that may not be obvious from the UI because the function does not revert or emit an error. It was discovered during a manual audit that examined the interaction between BoostAggregator and UniswapV3Staker and identified that the amountRequested != 0 guard was missing, allowing a zero value to act as a wildcard for full withdrawal. The bug is subtle because the function appears to behave correctly for non‑zero requests, and the zero‑value path is rarely exercised in normal operation, making it easy to overlook. To remediate the issue, the claimReward implementation should be changed to require a non‑zero amountRequested for any withdrawal, or alternatively to separate the “withdraw all” logic behind an explicit function that is protected by proper access controls. In conceptual terms, the fix involves eliminating the implicit “take everything” shortcut and ensuring that reward deductions are performed only when the caller explicitly specifies an amount that is less than or equal to the available balance. This aligns the contract with standard accounting assumptions that a user’s reward balance can only be reduced by a known, intended amount, preventing accidental or malicious total depletion of rewards.
