---
id: 1708
severity: "High"
---

# Wrong formula when add fee `incentivePool` can lead to loss of funds.

## Description

```solidity
incentivePool[tokenAddress] = (incentivePool[tokenAddress] + (amount * (transferFeePerc - tokenManager.getTokensInfo(tokenAddress).equilibriumFee))) / BASE_DIVISOR;
```
The `getAmountToTransfer` function of `LiquidityPool` updates `incentivePool[tokenAddress]` by adding some fee to it but the formula is wrong and the value of `incentivePool[tokenAddress]` will be divided by `BASE_DIVISOR` (10000000000) each time. After just a few time, the value of `incentivePool[tokenAddress]` will become zero and that amount of `tokenAddress` token will be locked in contract.

## Proof of Concept

Line 319-322
```solidity
incentivePool[tokenAddress] = (incentivePool[tokenAddress] + (amount * (transferFeePerc - tokenManager.getTokensInfo(tokenAddress).equilibriumFee))) / BASE_DIVISOR;
```
Let `x = incentivePool[tokenAddress]`, `y = amount`, `z = transferFeePerc` and `t = tokenManager.getTokensInfo(tokenAddress).equilibriumFee`. Then that be written as
```solidity
x = (x + (y * (z - t))) / BASE_DIVISOR;
x = x / BASE_DIVISOR + (y * (z - t)) / BASE_DIVISOR;
```

## Recommendation

```solidity
incentivePool[tokenAddress] += (amount * (transferFeePerc - tokenManager.getTokensInfo(tokenAddress).equilibriumFee)) / BASE_DIVISOR;
```

Great find, the wrong order of arithmetic operations deserves a severity of high as it would have serious negative consequences.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mis‑calculated update of the incentive pool balance inside the liquidity pool contract. Instead of adding the fee portion to the existing pool, the implementation adds the current pool balance together with the fee amount and then divides the sum by a large constant (BASE_DIVISOR = 10 000 000 000). Because the division is applied to the whole expression, each call to `getAmountToTransfer` reduces the stored `incentivePool` value by a factor of BASE_DIVISOR, eventually driving the balance to zero after only a few transactions. The root cause is the wrong order of arithmetic operations: the division is performed on the cumulative pool amount rather than on just the newly calculated fee. An attacker does not need to craft a special payload; any sequence of normal transfers that trigger the fee calculation will gradually erode the pool. As the pool shrinks, the protocol can no longer pay the promised incentives, effectively locking the associated tokens inside the contract. Users observing the UI will see that expected rewards or refunds are missing, balances that should increase remain unchanged, or the incentive amount appears as zero even though fees have been collected. The issue was uncovered during a formal security audit by Code4rena, where the auditors noticed that the incentive pool variable was being overwritten with a divided value instead of being incremented. This bug is subtle because a division operation is syntactically correct and may not raise compiler warnings, yet its semantic effect is a silent depletion of assets. To remediate, the contract should first compute the fee amount, divide it by BASE_DIVISOR, and then add the resulting value to the existing `incentivePool` (i.e., `incentivePool[token] += (amount * (transferFeePerc - equilibriumFee)) / BASE_DIVISOR;`). This change preserves the previously accumulated incentives and only adds the correctly scaled fee, preventing the accidental loss of funds. The vulnerability falls into the class of arithmetic‑order bugs that lead to incorrect accounting and asset locking, breaking the fundamental business assumption that incentive pools grow monotonically with collected fees.
