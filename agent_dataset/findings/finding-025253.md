---
id: 25253
severity: "Medium"
---

# Strategy withdraw may fail if weights of strategies differ from the real values and might lead to frozen ReservePool

## Description

When depositing or withdrawing in the ReservePool, it deposits/withdraws individually from the strategies based on the weights. In the case of withdrawals, the transaction might revert. Suppose default strategy with 50% weight and AaveV3 strategy with 50% weight. AaveV3 yield reduces, such that its amount is no longer 50%, but 49%.

In the [ReservePool, withdraw()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/ReservePool/GReservePool.sol#L191>), the transaction will revert because it tries to withdraw 50% from the AaveV3 strategy, [which will revert](<https://github.com/aave/aave-v3-core/blob/master/contracts/protocol/libraries/logic/ValidationLogic.sol#L102>).

## Proof of Concept

No PoC provided.

## Recommendation

Call the getBalance() (3S-GLACIER-H02), to get the maximum available balance and withdraw at most this amount. Then, return the actual withdrawn amount, so that [glAVAX](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L228-L234>) can deal with a possibly reduced amount.

Then, in glAVAX, it has to be dealt with accordingly. The max withdrawal amount check should be done in the ReservePool, so it is unnecessary to check again in glAVAX.
