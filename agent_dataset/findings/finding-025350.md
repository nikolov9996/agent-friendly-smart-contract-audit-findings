---
id: 25350
severity: "Low/Info"
---

# Aave and SavingsUsds strategies may revert when trying to withdraw all funds

## Description

Withdrawing all the Aave or Usds balance from the strategy may revert when there is yield. It withdraws first the fee to the treasury, which internally rounds up in Aave and SavingUsds, then it withdraws the remaining of the funds, but as it rounded up when withdrawing before, it will revert.

For confirmation, run testFork_aaveStrategy_withdraw_withFeesAndYield(), change warp to vm.warp(block.timestamp + 1980526); and just before the withdrawFromStrategy() call, add amountToWithdraw = aaveToken.balanceOf(address(aaveStrategy)) - fee;.

It will revert with 32, which is the [error](<https://github.com/aave-dao/aave-v3-origin/blob/main/src/contracts/protocol/libraries/helpers/Errors.sol#L40>) for not enough balance.

## Proof of Concept

No PoC provided.

## Recommendation

Either accept the issue and send a slightly smaller amount to withdraw or cap the withdrawal to the maximum withdrawal value after the fee has been collected to the treasury.
