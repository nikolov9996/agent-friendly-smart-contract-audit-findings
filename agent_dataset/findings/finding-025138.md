---
id: 25138
severity: "Low/Info"
---

# IWBTCZapper interface mismatches implementation

## Description



## Proof of Concept

## Vulnerability Detail

Several discrepancies exist between the interface and implementation:

1. `closeTroveFromCollateralWithWBTC` doesn't exist - it's `closeTroveFromCollateral`
2. `adjustTroveWithWBTC` has wrong arguments in the interface
3. Missing functions: `withdrawEvro`, `repayEvro`, `adjustZombieTroveWithWBTC`, `receiveFlashLoanOnCloseTroveFromCollateral`

## Impact

External integrations using the interface will fail to compile or call the wrong functions.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/Interfaces/IWBTCZapper.sol#L7-L13](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/Interfaces/IWBTCZapper.sol#L7-L13>)

```solidity
interface IWBTCZapper {
    // @audit - missing: withdrawEvro, repayEvro, adjustZombieTroveWithWBTC, receiveFlashLoanOnCloseTroveFromCollateral

    function adjustTroveWithWBTC(...) external;  // @audit - wrong arguments

    function closeTroveFromCollateralWithWBTC(...) external;  // @audit - doesn't exist, should be closeTroveFromCollateral
}
```

## Recommendation

Update the interface to match the implementation exactly.
