---
id: 25652
severity: "Crit/High"
---

# FluidLocker::_getUnlockingPercentage() incorrectly divides one of the components of the formula by S, leading to always having 80% penalty

## Description



## Proof of Concept

The component `(Math.sqrt(unlockPeriod  _SCALER) / _SCALER) <= sqrt(540  24  3600  1e18) / 1e18 = 0` is always null, so only `20*_SCALER` is left, which always yields a `20%` unlocking percentage.

## Impact

User suffers a big loss, even if they unlock with the maximum period, they will still get `80%` penalty.

## Recommendation

Remove the extra `_SCALER`.

```solidity
function _getUnlockingPercentage(uint128 unlockPeriod) internal pure returns (uint256 unlockingPercentageBP) {
    unlockingPercentageBP = (
        _PERCENT_TO_BP
            * (
                ((80 * _SCALER) / Math.sqrt(540 * _SCALER)) * (Math.sqrt(unlockPeriod * _SCALER))
                    + 20 * _SCALER
            )
    ) / _SCALER;
}
```
