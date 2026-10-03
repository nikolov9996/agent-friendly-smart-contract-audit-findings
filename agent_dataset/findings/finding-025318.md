---
id: 25318
severity: "Crit/High"
---

# Pool Delegates can steal all the pool's funds by setting a malicious Withdrawal Manager.

## Description

The current [PoolManager](<https://github.com/maple-labs/pool-v2-private/blob/6a7ae87df4f27cd924ee24f8d577e00b0b087512/contracts/PoolManager.sol>) contract allows the pool manager to change the withdrawalManager contract without any checks using the [setWithdrawalManager()](<https://github.com/maple-labs/pool-v2-private/blob/6a7ae87df4f27cd924ee24f8d577e00b0b087512/contracts/PoolManager.sol#L207>) function.

Since the withdrawal manager is responsible for holding the redeemable tokens and informing the pool which tokens can be redeemed, corrupting this contract gives complete control of the pool's funds to the pool delegate. Exploit scenario

- Pool delegate deposits one token into the Pool to get a single share
- Pool delegate sets a malicious withdrawal manager, allowing them to redeem a single share for the entire pool balance
- Pool delegate redeems their share and receives all the funds in the pool

## Proof of Concept

No PoC provided.

## Recommendation

Remove the setWithdrawalManager() function or pause it by default.
