---
id: 25558
severity: "Crit/High"
---

# Uneven getPendingAccFundingFees() leading to wrong funding rate update

## Description

Ostium uses a velocity funding rate [update](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L421>), so the actual change is the integral of the velocity of the past time.

There is a case when this update (which can be viewed as the area of the function, as shown in the [docs](<https://www.notion.so/ostium-defi/EXT-DUP-OIP-10-Velocity-based-funding-rate-552acfee594e4db58ce52033eb148493>)) is done incorrectly.

Namely, when absLastFundingRate is bigger than absNewFundingRate, the square part of the area (in the negative y axis), has side absNewFundingRate, but the docs and code use absLastFundingRate.

[Here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/poc-getPendingAccFundingFees-unevenAccumulatedChanged/test/foundry/OstiumPairInfos.t.sol#L1284>) is a poc. It can be seen that going from -5000 to 1000 gives a different change than -1000 to 5000.

## Proof of Concept

No PoC provided.

## Recommendation

Update the docs and tweak the code to accomodate for this change, such as:

```solidity
function getPendingAccFundingFees(uint16 pairIndex)
public
view
returns (int256 valueLong, int256 valueShort, int64 fr)
{
    ... if (absNewFundingRate > f.maxFundingFeePerBlock) {
        ... } else {
        ...

        uint256 squareHeight = absNewFundingRate < absLastFundingRate ? absNewFundingRate : absLastFundingRate;
        accumulated_funding_rate_change = int256( (squareHeight + (uint256(numBlocksToCharge).ceilDiv(2) * absLastVelocity)) * uint256(numBlocksToCharge) );
        ... }
}
```
