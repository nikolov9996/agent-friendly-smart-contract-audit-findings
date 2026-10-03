---
id: 25144
severity: "Medium"
---

# WBTCZapper precision loss will lead to reverts

## Description



## Proof of Concept

## Vulnerability Detail

The WBTCWrapper converts between 8-decimal WBTC and 18-decimal wWBTC by multiplying/dividing by 1e10. When a user provides `collAmount` that is not divisible by 1e10:

1. User deposits 1.5e10 wWBTC worth of collateral
2. Actual WBTC transferred = 1.5e10 / 1e10 = 1 WBTC (truncated)
3. Zapper wraps 1 WBTC → 1e10 wWBTC
4. Zapper tries to use `collAmount` (1.5e10) but only has 1e10 wWBTC
5. Transaction reverts

## Impact

Users must ensure their input amounts are divisible by 1e10 or transactions will revert.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L45](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L45>)

```solidity
function openTroveWithWBTC(OpenTroveParams calldata _params) external {
    // User provides _params.collAmount in wWBTC (18 decimals)
    // But WBTC transfer truncates to 8 decimals
    IWBTC(wbtcWrapper.WBTC()).transferFrom(msg.sender, address(this), _params.collAmount / 1e10);

    // Wrap back to wWBTC - may have less than _params.collAmount
    wbtcWrapper.depositFor(address(this), _params.collAmount / 1e10);

    // This may revert if there's not enough wWBTC
    borrowerOperations.openTrove(..., _params.collAmount, ...);
}
```

## Recommendation

Add input validation or round up the wrapped amount:

```solidity
function openTroveWithWBTC(OpenTroveParams calldata _params) external {
    require(_params.collAmount % 1e10 == 0, "Amount must be divisible by 1e10");
    // ... rest of function
}
```

Or round up to handle dust:

```solidity
uint256 wbtcAmount = _params.collAmount / 1e10;
uint256 actualWrappedAmount = wbtcAmount * 1e10;
// Use actualWrappedAmount instead of _params.collAmount
```
