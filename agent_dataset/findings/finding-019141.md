---
id: 19141
severity: "High"
---

# Incorrect precision assumed from RdpxPriceOracle creates multiple issues related to value inflation/deflation

## Description

The `RdpxEthPriceOracle`, available in the audit repo [here](https://github.com/dopex-io/rdpx-eth-oracle/blob/5762c2339b1c45b87ff4db172e43cef4a0ff603a/src/RdpxEthOracle.sol), provides the `RdpxV2Core`, the `UniV2LiquidityAmo` and the `PerpetualAtlanticVault` contracts the necessary values for `rdpx` related price calculations.

The issue is that these contracts expect the returned values to be in `1e8` precision (as stated in the natspec [here](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/core/RdpxV2Core.sol#L1224), [here](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/amo/UniV2LiquidityAmo.sol#L378) and [here](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/perp-vault/IPerpetualAtlanticVault.sol#L20C1-L24C65)). But the returned precision [is actually `1e18`](https://github.com/dopex-io/rdpx-eth-oracle/blob/5762c2339b1c45b87ff4db172e43cef4a0ff603a/src/RdpxEthOracle.sol#L243).

This difference creates multiple issues throughout the below contracts:

Contract | Function | Effect  
---|---|---  
`rdpxV2Core.sol` | `getRdpxPrice()` | Returns an `1e18` value when `1e8` expected  
| `calculateBondCost()` | Deflates the `rdpxRequired`  
| `calculateAmounts()` | Inflates the `rdpxRequiredInWeth`  
| `_transfer()` | Inflates `rdpxAmountInWeth` and may cause possible underflow  
`UniV2LiquidityAmo` | `getLpPriceInEth()` | Overestimates the lp value  
`ReLp.sol` | `reLP()` | Inflates min token amounts  
`PerpetualAtlanticVault.sol` | `getUnderlyingPrice()` | Returns `1e18` instead of `1e8`  
| `calculatePremium()` | Inflates the premium calculation

## Proof of Concept

The `RdpxEthPriceOracle.sol` file can be found [here](https://github.com/dopex-io/rdpx-eth-oracle/blob/5762c2339b1c45b87ff4db172e43cef4a0ff603a/src/RdpxEthOracle.sol)

It exposes the following functions used in the audit:

  * [`getLpPriceInEth()`](https://github.com/dopex-io/rdpx-eth-oracle/blob/5762c2339b1c45b87ff4db172e43cef4a0ff603a/src/RdpxEthOracle.sol#L200)
  * [`getRdpxPriceInEth()`](https://github.com/dopex-io/rdpx-eth-oracle/blob/5762c2339b1c45b87ff4db172e43cef4a0ff603a/src/RdpxEthOracle.sol#L243)

These two functions provide the current price denominated in `ETH`, with a precision in `1e18`, as confirmed by their respective natspec comments:
    
```solidity
/// @dev Returns the price of LP in ETH in 1e18 decimals
function getLpPriceInEth() external view override returns (uint) {
...
```
    
```solidity
/// @notice Returns the price of rDPX in ETH
/// @return price price of rDPX in ETH in 1e18 decimals
function getRdpxPriceInEth() external view override returns (uint price) {
```

But, in the contracts from the audit repo, the business logic (and even the natspec) assumes the returned precision will be `1e8`. See below:

In the `RdpxV2Core` contract the assumption that the price returned from the oracle is clearly noted in the [natspec](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/core/RdpxV2Core.sol#L1227C1-L1227C1) of the `getRdpxPrice()` function:
    
```solidity
/**
 * @notice Returns the price of rDPX against ETH
 * @dev    Price is in 1e8 Precision
 * @return rdpxPriceInEth rDPX price in ETH
 **/
function getRdpxPrice() public view returns (uint256) {
  return
    IRdpxEthOracle(pricingOracleAddresses.rdpxPriceOracle)
      .getRdpxPriceInEth();
}
```

In `UniV2LiquidityAmo` the assumption is noted [here](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/amo/UniV2LiquidityAmo.sol#L378):
    
```solidity
/**
 * @notice Returns the price of a rDPX/ETH Lp token against the alpha token
 * @dev    Price is in 1e8 Precision
 * @return uint256 LP price
 **/
function getLpPrice() public view returns (uint256) {
```

And it has business logic implication here:
    
```solidity
function getLpTokenBalanceInWeth() external view returns (uint256) {
  return (lpTokenBalance * getLpPrice()) / 1e8;
}
```

In `PerpetualAtlanticVault` it is noted [here](https://github.com/code-423n4/2023-08-dopex/blob/eb4d4a201b3a75dd4bddc74a34e9c42c71d0d12f/contracts/perp-vault/IPerpetualAtlanticVault.sol#L21):
    
```solidity
/**
 * @notice Returns the price of the underlying in ETH in 1e8 precision
 * @return uint256 the current underlying price
 **/
function getUnderlyingPrice() external view returns (uint256);
```

And the business logic implications in this contract are primarily found in the `calculatePremium` function, where the premium is divided by `1e8`:
    
```solidity
function calculatePremium(
  uint256 _strike,
  uint256 _amount,
  uint256 timeToExpiry,
  uint256 _price
) public view returns (uint256 premium) {
  premium = ((IOptionPricing(addresses.optionPricing).getOptionPrice(
    _strike,
    _price > 0 ? _price : getUnderlyingPrice(),
    getVolatility(_strike),
    timeToExpiry
  ) * _amount) / 1e8);
}
```

From the audit files it’s clear that the assumption was that the returned price would be in `1e8`, but this is Dopex’s own `RdpxPriceOracle`, so was likely a simple oversight which slipped through testing as a `MockRdpxEthPriceOracle` was implemented to simplify testing, which mocked the values from the oracle, but only to a `1e8` precision.

## Recommendation

For price feeds where `WETH` will be token B, it is convention (although not a standard, as far as the reviewer is aware), that the precision returned will be `1e18`. See [here](https://ethereum.stackexchange.com/questions/92508/do-all-chainlink-feeds-return-prices-with-8-decimals-of-precision).

As the sponsor indicated that the team might move to Chainlink oracles, it is suggested to modify the `RdpxV2Core`, `PerpetualAtlanticVault`, `UniV2Liquidity` and the `ReLp` contracts to work with the returned `1e18` precision, assuming that the keep the token pair as rdpx/WETH.

The issue is in the oracle contract which returns 1e18.

Seems like the Warden grouped a bunch of consequences down to the root cause of the oracle precision.
 
I’ll need to determine how to group / ungroup findings as there seem to be multple impacts but a single root cause.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision mismatch between the RdpxEthPriceOracle and the contracts that consume its price data. The oracle returns prices with 18 decimal places (1e18 precision) while RdpxV2Core, UniV2LiquidityAmo, ReLp and PerpetualAtlanticVault all assume the values are expressed with 8 decimal places (1e8 precision), as documented in their NatSpec comments. This discrepancy originates from an oversight in the oracle implementation and the reliance on a mock oracle during testing that used the wrong scale. When a contract reads the 1e18 price and treats it as 1e8, every downstream calculation that divides or multiplies by 1e8 produces values that are off by a factor of 1e10. For example, getRdpxPrice() returns an inflated price, causing calculateBondCost() to deflate the required rdpx amount, calculateAmounts() to inflate the rdpxRequiredInWeth, and _transfer() to inflate rdpxAmountInWeth which can lead to under‑flow errors. In the AMO, getLpPriceInEth() overestimates the LP token value, making reLP() report excessively high minimum token amounts. In the perpetual vault, getUnderlyingPrice() returns a value ten‑billion times larger than expected, which inflates the premium calculation in calculatePremium(). From a user’s perspective this manifests as unexpected zero or tiny refunds, excessively high premium quotes, LP token balances that appear larger than they should be, or transactions that revert due to under‑flow. The bug affects any participant interacting with the core protocol – bond purchasers, liquidity providers, option traders and vault users – because the core accounting logic is corrupted. It was discovered during a formal audit when reviewers compared the NatSpec precision declarations with the actual return values of the oracle and observed that the mock oracle used in tests hid the problem. The issue is subtle because both the oracle and the consuming contracts compile and run without errors; only the financial outcomes reveal the mismatch, making it easy to miss in functional testing. The proper fix is to align the precision expectations: either modify the oracle to return 1e8 values or, more appropriately, update all consuming contracts to handle 1e18 precision consistently, adjusting division factors and any scaling logic accordingly. This correction restores the intended accounting invariants and prevents inflated or deflated price‑derived calculations, ensuring that users receive correct refunds, premiums and LP valuations.
