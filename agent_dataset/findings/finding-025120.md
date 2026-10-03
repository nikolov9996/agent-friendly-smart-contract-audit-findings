---
id: 25120
severity: "Crit/High"
---

# Users will steal excess funds from the Vault due to VaultPoolLib::redeem() not always decreasing self.withdrawalPool.raBalance and self.withdrawalPool.paBalance

## Description



## Proof of Concept

`__tryRedeemExcessFromAmmPool()` does not decrease the withdrawn `self.withdrawalPool.raBalance` and `self.withdrawalPool.paBalance`.

```solidity
function __tryRedeemExcessFromAmmPool(VaultPool storage self, uint256 amountAttributed, uint256 excessAmount)
    internal
    view
    returns (uint256 ra, uint256 pa, uint256 withdrawnFromAmm)
{
    (ra, pa) = __tryRedeemfromWithdrawalPool(self, amountAttributed);

    withdrawnFromAmm =
        MathHelper.calculateRedeemAmountWithExchangeRate(excessAmount, self.withdrawalPool.raExchangeRate); //@audit PA is ignored here

    ra += withdrawnFromAmm;
}
```

## Recommendation

Replace `tryRedeemfromWithdrawalPool()`** with ``**`redeemfromWithdrawalPool()`.

```solidity
function __tryRedeemExcessFromAmmPool(VaultPool storage self, uint256 amountAttributed, uint256 excessAmount)
    internal
    view
    returns (uint256 ra, uint256 pa, uint256 withdrawnFromAmm)
{
    (ra, pa) = __redeemfromWithdrawalPool(self, amountAttributed);

    withdrawnFromAmm =
        MathHelper.calculateRedeemAmountWithExchangeRate(excessAmount, self.withdrawalPool.raExchangeRate); //@audit PA is ignored here

    ra += withdrawnFromAmm;
}
```
