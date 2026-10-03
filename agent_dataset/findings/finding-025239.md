---
id: 25239
severity: "Medium"
---

# In GReservePool, if a strategy is frozen reserve pool stops working

## Description

If a strategy stops working it will become impossible to use the Reserve Pool. The functions deposit(), [withdraw()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L252>) and withdrawAll() will no longer work.

This problem will also affect the contract glAVAX which will make the functions rebalance() and withdraw() not work as those functions can call the broken functions of the Reserve Pool. There is the possibility of the third party application that is being used by the strategy to stop working.

Which will leave the funds in the third party application, making you wait for it to recover, and in the meantime the code will revert.

## Proof of Concept

No PoC provided.

## Recommendation

It would be best in this scenario to remove strategies from the reserve pool (keeping them from reverting), this would be possible using the rebalance() function suggested in 3S-GLACIER-L03 and the fact that applications,like aave, allow for withdrawals if it is frozen.

For this we would add a removeBrokenStrategy() that would call a function in the strategy to try and withdraw the funds, and would remove the strategy from the list.

In the strategy a new function called handleBroken() would try to withdraw the funds so they can be distrib uted among the other strategies (this function would be tailored to what protocol is being used). A function would also need to be added to return the broken strategy back into the reserve pool.
