---
id: 18295
severity: "High"
---

# Exchange: `totalFunding` calculation should be done with a simple multiplication operation instead of a `wadMul` operation

## Description

`wad` operations are meant to be done with int/uint which represent numbers with 18 decimals.

While the funding rate follows this representation, a simple time difference does not.

In `Exchange.getMarkPrice` as well as in `Exchange._updateFundingRate` a `wadMul` operation is done to multiply the funding rate per second by a simple time difference, leading to wrong calculation of `normalizationFactor` and mark price, affecting critical parts of the protocol.

## Proof of Concept

In `Exchange.getMarkPrice` first we get the funding rate per second:

```solidity
(int256 fundingRate,) = getFundingRate();
fundingRate = fundingRate / 1 days; // Funding rate per second
```

Immediately after, the total funding since last update is calculated:

```solidity
int256 currentTimeStamp = int256(block.timestamp);
int256 fundingLastUpdatedTimestamp = int256(fundingLastUpdated);

// @audit funding rate X (time interval) / 1e18 = Number without decimal
int256 totalFunding = wadMul(fundingRate, (currentTimeStamp - fundingLastUpdatedTimestamp));
```

`int256 totalFunding = wadMul(fundingRate, (currentTimeStamp - fundingLastUpdatedTimestamp));`  
is the same that  
$TOTAL\_ FUNDING\_{t\_{1}; t\_{2}} = \frac{FUNDING\_ RATE\_{sec} \times (t\_{2} - t\_{1})}{10^{18}}$

However, the division by $10^{18}$ should not happen, given that time difference does not represent a number with 18 decimals.

This ends up in a miscalculation of `totalFunding` variable, and as a consequence, a miscalculation of mark price.

The same issue happens in `_updateFundingRate` function.

## Recommendation

Simply replace current `wad` operation for a simple multiplication.

```solidity
function getMarkPrice() public view override returns (uint256 markPrice, bool isInvalid) {
    // Get base asset price from oracles
    (uint256 baseAssetPrice, bool invalid) = pool.baseAssetPrice();
    isInvalid = invalid;

    // Get funding rate per second
    // max 1% or 1e16
    (int256 fundingRate,) = getFundingRate();
    fundingRate = fundingRate / 1 days;

    int256 currentTimeStamp = int256(block.timestamp);
    int256 fundingLastUpdatedTimestamp = int256(fundingLastUpdated);

    int256 totalFunding = fundingRate * (currentTimeStamp - fundingLastUpdatedTimestamp);
    int256 normalizationUpdate = 1e18 - totalFunding;
    uint256 newNormalizationFactor = normalizationFactor.mulWadDown(uint256(normalizationUpdate));

    uint256 squarePrice = baseAssetPrice.mulDivDown(baseAssetPrice, PRICING_CONSTANT);
    markPrice = squarePrice.mulWadDown(newNormalizationFactor);
}

function _updateFundingRate() internal {
    (int256 fundingRate,) = getFundingRate();
    
    fundingRate = fundingRate / 1 days;

    int256 currentTimeStamp = int256(block.timestamp);
    int256 fundingLastUpdatedTimestamp = int256(fundingLastUpdated);

    int256 totalFunding = fundingRate * (currentTimeStamp - fundingLastUpdatedTimestamp);
    
    int256 normalizationUpdate = 1e18 - totalFunding;

    normalizationFactor = normalizationFactor.mulWadDown(uint256(normalizationUpdate));
    
    emit UpdateFundingRate(fundingLastUpdated, normalizationFactor);
    fundingLastUpdated = block.timestamp;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect arithmetic operation used to compute the cumulative funding adjustment in the Exchange contract. The contract stores the funding rate as a signed 18‑decimal fixed‑point number (wad) and correctly converts the per‑second rate by dividing the raw rate by 1 day. However, when the contract later multiplies this per‑second rate by the elapsed time since the last update, it uses the generic wadMul helper, which assumes both operands are 18‑decimal numbers. The elapsed time is a plain integer representing seconds and does not carry 18‑decimal precision, so wadMul implicitly divides the product by 1e18. This extra division yields a totalFunding value that is many orders of magnitude smaller than the true funding amount. The underestimated totalFunding is then subtracted from 1e18 to form a normalizationUpdate, which is fed into mulWadDown to adjust the normalizationFactor and ultimately the mark price. Because the normalization factor is wrong, the reported mark price deviates from the mathematically correct price. The deviation propagates to any downstream logic that relies on the mark price, such as liquidation checks, margin calculations, and fee assessments. From a user’s perspective, a trader may see a price that is unexpectedly low or high, may be liquidated when the position should be safe, or may notice that their expected funding payments never materialise, effectively causing funds to disappear or balances to be incorrectly adjusted. The bug manifests whenever getMarkPrice or _updateFundingRate is called after a non‑zero time interval, i.e., any normal operation of the protocol after the funding rate has been set. All participants—traders, liquidity providers, and the protocol itself—are affected because the core accounting invariant that funding payments balance long and short positions is broken. The issue was identified during a formal security audit (Code4rena) by noticing that the wadMul call was applied to a raw timestamp difference, a pattern that does not match the intended fixed‑point semantics. It is subtle because the contract still compiles and runs, and the price error may only become apparent after several hours or days of operation, making it easy to attribute to market volatility rather than a calculation bug. The proper remediation is to replace the wadMul call with a plain integer multiplication (fundingRate * timeDelta) and keep the subsequent scaling consistent with the 18‑decimal representation of the funding rate. In conceptual terms, the fix removes the unintended 1e18 divisor, ensuring that totalFunding reflects the true cumulative funding amount, restoring correct normalizationFactor updates, and guaranteeing that the mark price aligns with the intended economic model. This class of bug belongs to the broader category of fixed‑point arithmetic misuse, where developers apply generic high‑precision multiplication to operands that are not uniformly scaled, leading to systematic under‑ or over‑flows in financial calculations.
