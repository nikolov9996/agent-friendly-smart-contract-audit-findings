---
id: 25374
severity: "Medium"
---

# TradingLimits::update() incorrectly only rounds up when deltaFlowUnits becomes 0, which will silently increase trading limits

## Description



## Proof of Concept

`TradingLimits::update()` only rounds up when `deltaFlowUnits` becomes 0.

```solidity
function update(
  ITradingLimits.State memory self,
  ITradingLimits.Config memory config,
  int256 _deltaFlow,
  uint8 decimals
) internal view returns (ITradingLimits.State memory) {
  int256 _deltaFlowUnits = _deltaFlow / int256((10 ** uint256(decimals)));
  require(_deltaFlowUnits <= MAX_INT48, "dFlow too large");

  int48 deltaFlowUnits = int48(_deltaFlowUnits);
  if (deltaFlowUnits == 0) {
    deltaFlowUnits = _deltaFlow > 0 ? int48(1) : int48(-1);
  }
  ...
```

## Impact

The trading limits may be severely bypassed with malicious intent (by double the amount) or by a smaller but still significant amount organically.

## Recommendation

The correct fix is:

```solidity
int256 _deltaFlowUnits = (_deltaFlow - 1) / int256((10 ** uint256(decimals))) + 1;
```
