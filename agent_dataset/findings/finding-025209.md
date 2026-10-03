---
id: 25209
severity: "Crit/High"
---

# Wrong transformation in function previewMintDebt(...)

## Description

In the BorrowingVault.sol the function previewMintDebt(...) is supposed to take an amount of shares and turn them into an amount of debt. Currently it is taking the shares as if they were debt and turning them to shares.

```solidity
function previewMintDebt(uint256 shares) public view override returns
(uint256 debt) {
    return _convertDebtToShares(shares, Math.Rounding.Down);
}
```

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
