---
id: 25146
severity: "Medium"
---

# WBTCZapper decimal mismatch causes revert

## Description



## Proof of Concept

## Vulnerability Detail

The `closeTroveFromCollateral()` function calculates `collLeft` by subtracting `flashLoanAmount` (8 decimals, WBTC) from `trove.entireColl` (18 decimals, wWBTC). This decimal mismatch causes:

1. If `entireColl` is e.g. `1e18` (1 wWBTC) and `flashLoanAmount` is `1e8` (1 WBTC), then `collLeft = 1e18 - 1e8 ≈ 1e18` - almost the entire collateral
2. The `minExpectedCollateral` check becomes meaningless as `collLeft` is always near `entireColl`
3. When sending `collLeft` to the user, the transaction will revert because the contract doesn't have that much wWBTC

## Impact

Users cannot close their troves using the flash loan mechanism, or if the function somehow proceeds, the slippage protection is bypassed.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L340](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L340>)

```solidity
function closeTroveFromCollateral(CloseTroveFromCollateralParams calldata _params) external {
    // ...

    LatestTroveData memory trove = troveManager.getLatestTroveData(_params.troveId);

    // @audit - trove.entireColl is in 18 decimals (wWBTC)
    // @audit - _params.flashLoanAmount is in 8 decimals (WBTC)
    uint256 collLeft = trove.entireColl - _params.flashLoanAmount;  // WRONG!

    require(collLeft >= _params.minExpectedCollateral, "Insufficient collateral");

    // ...
}
```

## Recommendation

Convert `flashLoanAmount` to 18 decimals before subtraction:

```solidity
function closeTroveFromCollateral(CloseTroveFromCollateralParams calldata _params) external {
    // ...

    LatestTroveData memory trove = troveManager.getLatestTroveData(_params.troveId);

    // Convert flashLoanAmount from 8 decimals to 18 decimals
    uint256 flashLoanAmountWrapped = _params.flashLoanAmount * 1e10;
    uint256 collLeft = trove.entireColl - flashLoanAmountWrapped;

    require(collLeft >= _params.minExpectedCollateral, "Insufficient collateral");

    // ...
}
```
