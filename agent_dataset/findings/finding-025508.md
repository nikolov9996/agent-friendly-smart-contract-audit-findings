---
id: 25508
severity: "Low/Info"
---

# utilizationThresholdP of 10_000 will make OstiumPairInfos::_getUtilizationOpeningFee() divide by 0

## Description

[utilizationThresholdP](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L125>) should never be set to the max 10_000 or it will lead to division by 0 when calling [OstiumPairInfos::_getUtilizationOpeningFee()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L382-L390>).

## Proof of Concept

No PoC provided.

## Recommendation

Add an equality restriction to utilizationThresholdP:

```solidity
if ( ...
|| value.utilizationThresholdP >= MAX_USAGE_THRESHOLDP ... //@audit
note the = ) {
revert WrongParams();
}
```
