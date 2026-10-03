---
id: 25143
severity: "Medium"
---

# WBTCZapper approves wrong token for exchange

## Description



## Proof of Concept

## Vulnerability Detail

In the constructor, the zapper approves wWBTC to the exchange contract. However, the Curve NG pool on Gnosis holds WBTC (8 decimals), not wWBTC (18 decimals). When `closeTroveFromCollateral()` tries to swap collateral for EVRO, it will fail because WBTC is not approved.

## Impact

The `closeTroveFromCollateral()` function will fail when trying to swap WBTC for EVRO, preventing users from closing their troves using the flash loan mechanism.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L29](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/Zappers/WBTCZapper.sol#L29>)

```solidity
constructor(IAddressesRegistry _addressesRegistry, IFlashLoanProvider _flashLoanProvider, IExchange _exchange)
    BaseZapper(_addressesRegistry, _flashLoanProvider, _exchange)
{
    // Approve wWBTC to exchange
    collToken.approve(address(_exchange), type(uint256).max);  // @audit - wrong token!
}
```

## Recommendation

Approve WBTC instead of wWBTC for the exchange:

```solidity
constructor(IAddressesRegistry _addressesRegistry, IFlashLoanProvider _flashLoanProvider, IExchange _exchange)
    BaseZapper(_addressesRegistry, _flashLoanProvider, _exchange)
{
    // Approve WBTC to exchange (for closeTroveFromCollateral)
    IWBTC(wbtcWrapper.WBTC()).approve(address(_exchange), type(uint256).max);

    // Approve wWBTC for borrowerOperations (existing functionality)
    collToken.approve(address(borrowerOperations), type(uint256).max);
}
```
