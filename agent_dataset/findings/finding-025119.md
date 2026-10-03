---
id: 25119
severity: "Crit/High"
---

# Users redeeming early will withdraw Ra without decreasing the amount locked, which will lead to stolen funds when withdrawing after expiry

## Description



## Proof of Concept

`PsmLib::lvRedeemRaWithCtDs()` does not reduce the amount of `Ra` locked.

```solidity
function lvRedeemRaWithCtDs(State storage self, uint256 amount, uint256 dsId) internal {
    DepegSwap storage ds = self.ds[dsId];
    ds.burnBothforSelf(amount);
}
```

## Impact

Users withdraw more funds then they should via `PsmLib::redeemWithCt()` meaning the last users can not withdraw.

## Recommendation

`PsmLib::lvRedeemRaWithCtDs()` must reduce the amount of `Ra` locked.

```solidity
function lvRedeemRaWithCtDs(State storage self, uint256 amount, uint256 dsId) internal {
    self.psm.balances.ra.decLocked(amount);
    DepegSwap storage ds = self.ds[dsId];
    ds.burnBothforSelf(amount);
}
```
