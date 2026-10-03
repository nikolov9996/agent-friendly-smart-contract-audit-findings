---
id: 25274
severity: "Low/Info"
---

# A decrease in updateCollateralInterval will lead to unfair penalties

## Description

The MinterGateway.updateCollateral function should be called once every updateCollateralInverval. If the minter fails to do this a penalty will be imposed on him next time he tries to update his collateral.

This process is done through [MinterGateway._imposePenaltyIfMissedCollateralUpdates](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L675>) function.

This function will in turn call [MinterGateway._getMissedCollateralUpdateParameters](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L824>) to calculate the amount of intervals missed:

```solidity
function _getMissedCollateralUpdateParameters( uint40 lastUpdateTimestamp_, uint40 lastPenalizedUntil_, uint32 updateInterval_ ) internal view returns (uint40 missedIntervals_, uint40 missedUntil_) {
    uint40 penalizeFrom_ = UIntMath.max40(lastUpdateTimestamp_, lastPenalizedUntil_);
    // If brand new minter or `updateInterval_` is 0, then there is no
missed interval charge at all.
if (lastUpdateTimestamp_ == 0 || updateInterval_ == 0) return (0, penalizeFrom_);
uint40 timeElapsed_ = uint40(block.timestamp) - penalizeFrom_;
if (timeElapsed_ < updateInterval_) return (0, penalizeFrom_);
missedIntervals_ = timeElapsed_ / updateInterval_;
missedUntil_ = penalizeFrom_ + (missedIntervals_ * updateInterval_);
}
```

The issue with this function arises when there's a decrease in updateCollateralInterval. It incorrectly assumes that the minter missed one or more intervals in the past based on the new updateCollateralInterval, even though this new value only became effective later on.

This will impose a penalty to the minter as if he missed updates to his collateral, when in reality he did not. Here's an example:

- On January 1st, TTG executes a proposal that sets updateCollateralInterval to 1

```solidity
month;
- On January 28th, Bob calls updateCollateral;
- On February 28th, Bob calls updateCollateral again;
```

- On March 27th, TTG executes a proposal that reduces updateCollateralInterval to 1 day;
- On March 28th, Bob calls updateCollateral so that he does not miss the new interval. This last call, however, will impose an unfair penalty on Bob of 28 missedIntervals_ when he did not missed any.

## Proof of Concept

No PoC provided.

## Recommendation

Change the logic in _getMissedCollateralUpdateParameters so that it checks if there was any decrease in updateCollateralInterval and, if so, calculate if there was any missed intervals before the proposal execution, using the old updateCollateralInterval.

After that it should procede to calculate the amount of misssedIntervals_ after the proposal execution using the new updateCollateralInterval.
