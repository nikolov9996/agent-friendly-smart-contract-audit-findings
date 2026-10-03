---
id: 25111
severity: "Crit/High"
---

# VaultPoolLib::reserve() will store the Pa not attributed to user withdrawals incorrectly and leave in untracked once it expires again

## Description



## Proof of Concept

`VaultPoolLib::rationedToAmm()` does not deal with the `Pa`.

```solidity
function rationedToAmm(VaultPool storage self, uint256 ratio) internal view returns (uint256 ra, uint256 ct) {
    uint256 amount = self.ammLiquidityPool.balance;

    (ra, ct) = MathHelper.calculateProvideLiquidityAmountBasedOnCtPrice(amount, ratio);
}
```

## Impact

The `Pa` in the `Vault` is stuck.

## Recommendation

Distributed the `Pa` to users based on their `LV` shares or redeem the `Pa` for `Ra` and add liquidity to the new issued `Ds` or similar.
