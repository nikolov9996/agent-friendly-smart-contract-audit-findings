---
id: 25140
severity: "Crit/High"
---

# SDAIPriceFeed is vulnerable to donation attack via manipulatable vault rate

## Description



## Proof of Concept

## Vulnerability Detail

The `SDAIPriceFeed` calculates the sDAI price using the ERC4626 vault's `convertToAssets()` function, which returns the current exchange rate between sDAI shares and DAI assets. This rate can be manipulated by donating assets directly to the vault.

Attack scenario:

1. Attacker deposits 500 sDAI when vault has 500 sDAI shares and 500 DAI (1:1 rate)
2. Attacker donates 9000 DAI directly to the vault
3. Now 1000 sDAI shares = 10000 DAI (1:10 rate)
4. Attacker opens a trove with 1000 sDAI and borrows 10000 EVRO at the inflated rate
5. Attacker redeems the 10000 EVRO against other collaterals, draining the protocol

## Impact

An attacker can manipulate the sDAI price to borrow significantly more EVRO than the collateral is worth, then redeem against other collaterals to drain the protocol.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/SDAIPriceFeed.sol#L47](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/SDAIPriceFeed.sol#L47>)

```solidity
function _fetchPricePrimary() internal returns (uint256, bool) {
    assert(priceSource == PriceSource.primary);

    (uint256 daiUSDPrice, bool daiEurOracleDown) = _getOracleAnswer(ethUsdOracle);
    (uint256 eurUsdPrice, bool eurUsdOracleDown) = _getOracleAnswer(eurUsdOracle);

    // Get the DAI rate of the SDAI vault
    uint256 sdaiDaiRate = sdai.convertToAssets(1e18);  // @audit - manipulatable!

    // ...

    uint256 sdaiUSDPrice = FixedPointMathLib.mulWadUp(daiUSDPrice, sdaiDaiRate);
    lastGoodPrice = FixedPointMathLib.divWad(sdaiUSDPrice, eurUsdPrice);

    return (lastGoodPrice, false);
}
```

## Recommendation

Use the max price between an oracle rate and the instantaneous rate for redemptions, and the min price for calculating ICR when opening/adjusting troves:

```solidity
function _fetchPricePrimary(bool _isRedemption) internal returns (uint256, bool) {
    uint256 sdaiDaiRate = sdai.convertToAssets(1e18);
    (uint256 oracleRate, bool oracleDown) = _getOracleAnswer(sdaiOracle);

    uint256 rateToUse;
    if (_isRedemption) {
        rateToUse = LiquityMath._max(sdaiDaiRate, oracleRate);
    } else {
        rateToUse = LiquityMath._min(sdaiDaiRate, oracleRate);
    }
    // ... rest of calculation
}
```
