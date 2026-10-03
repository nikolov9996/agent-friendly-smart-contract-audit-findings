---
id: 25123
severity: "Medium"
---

# Withdrawing all lv before expiry will lead to lost funds in the Vault

## Description



## Proof of Concept

The `MathHelper` separates liquidity by calculating first the `ratePerLv`, which will trigger a division by 0 revert.

```solidity
function separateLiquidity(uint256 totalAmount, uint256 totalLvIssued, uint256 totalLvWithdrawn)
    external
    pure
    returns (uint256 attributedWithdrawal, uint256 attributedAmm, uint256 ratePerLv)
{
    // with 1e18 precision
    ratePerLv = ((totalAmount * 1e18) / totalLvIssued);

    // attribute all to AMM if no lv issued or withdrawn
    if (totalLvIssued == 0 || totalLvWithdrawn == 0) {
        return (0, totalAmount, ratePerLv);
    }
    ...
}
```

## Recommendation

The `MathHelper` should place the return guard first:

```solidity
function separateLiquidity(uint256 totalAmount, uint256 totalLvIssued, uint256 totalLvWithdrawn)
    external
    pure
    returns (uint256 attributedWithdrawal, uint256 attributedAmm, uint256 ratePerLv)
{
    // attribute all to AMM if no lv issued or withdrawn
    if (totalLvIssued == 0 || totalLvWithdrawn == 0) {
        return (0, totalAmount, 0);
    }
    ...
    // with 1e18 precision
    ratePerLv = ((totalAmount * 1e18) / totalLvIssued);
}
```
