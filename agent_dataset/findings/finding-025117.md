---
id: 25117
severity: "Medium"
---

# Rebasing tokens are not supported contrary to the readme and will lead to loss of funds

## Description



## Proof of Concept

`State.sol` tracks the balances:

```solidity
struct Balances {
    PsmRedemptionAssetManager ra;
    uint256 dsBalance;
    uint256 ctBalance;
    uint256 paBalance;
}
```

## Recommendation

Don't set rebasing tokens are `Ra` or `Pa` or implement a way to sync the balances.
