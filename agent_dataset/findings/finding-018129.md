---
id: 18129
severity: "High"
---

# `RewardThrottle.checkRewardUnderflow

## Description

```solidity
function checkRewardUnderflow() public onlyActive {
  uint256 epoch = timekeeper.epoch();

  uint256 _activeEpoch = activeEpoch; // gas

  // Fill in gaps so we have a fresh foundation to calculate from
  _fillInEpochGaps(epoch);

  if (epoch > _activeEpoch) {
    for (uint256 i = _activeEpoch; i < epoch; ++i) {
      uint256 underflow = _getRewardUnderflow(i);

      if (underflow > 0) {
        uint256 balance = overflowPool.requestCapital(underflow);

        _sendToDistributor(balance, i);  // @audit cumulative apr will be tracked wrongly when epoch > _activeEpoch + 1
      }
    }
  }
}
```

`RewardThrottle.checkRewardUnderflow()` might calculate the cumulative `APR`s for epochs wrongly.

As a result, `cashflowAverageApr` will be calculated incorrectly in `updateDesiredAPR()`, and `targetAPR` would be changed unexpectedly.

## Proof of Concept

In `checkRewardUnderflow()`, it calls a `_sendToDistributor()` function to update cumulative `APR`s after requesting some capitals from the overflow pool.

File: 2023-02-malt\contracts\RewardSystem\RewardThrottle.sol
445:     if (epoch > _activeEpoch) {
446:       for (uint256 i = _activeEpoch; i < epoch; ++i) {
447:         uint256 underflow = _getRewardUnderflow(i);
448: 
449:         if (underflow > 0) {
450:           uint256 balance = overflowPool.requestCapital(underflow);
451: 
452:           _sendToDistributor(balance, i);  // @audit cumulative apr will be tracked wrongly when epoch > _activeEpoch + 1
453:         }
454:       }
455:     }

The main reason for this issue is that `_sendToDistributor()` doesn’t update the cumulative `APR`s when `amount == 0` and the below scenario would be possible.

1. Let’s assume `activeEpoch = 100` and `epoch = 103`. It’s possible if the active epoch wasn’t updated for 2 epochs.
2. After that, the `checkRewardUnderflow()` function will call `_fillInEpochGaps()` and the cumulative `APR`s will be settled accordingly.
3. And it will try to request capitals from the `overflowPool` and increase the rewards for epochs.
4. At epoch 100, it requests some positive `balance` from `overflowPool` and increases the cumulative `APR`s for epoch 101 correctly in `_sendToDistributor()`.

File: 2023-02-malt\contracts\RewardSystem\RewardThrottle.sol
611:     state[epoch].rewarded = state[epoch].rewarded + rewarded;
612:     state[epoch + 1].cumulativeCashflowApr = 
613:       state[epoch].cumulativeCashflowApr +
614:       epochCashflowAPR(epoch);
615:     state[epoch + 1].cumulativeApr = 
616:       state[epoch].cumulativeApr +
617:       epochAPR(epoch);
618:     state[epoch].bondedValue = bonding.averageBondedValue(epoch);

5. After that, the `overflowPool` doesn’t have any remaining funds and the `balance(At L450)` will be 0 for epochs 101, 102.
6. So `_sendToDistributor()` will be terminated right away and won’t increase the cumulative `APR`s of epoch 102 according to epoch 101 and this value won’t be changed anymore because the `activeEpoch` is 103 already.

File: 2023-02-malt\contracts\RewardSystem\RewardThrottle.sol
575:   function _sendToDistributor(uint256 amount, uint256 epoch) internal { 
576:     if (amount == 0) {
577:       return;
578:     }

As a result, the cumulative `APR`s will save smaller values from epoch 102 and `cashflowAverageApr` will be smaller also if the `smoothingPeriod` contains such epochs in `updateDesiredAPR()`.

File: 2023-02-malt\contracts\RewardSystem\RewardThrottle.sol
139:     uint256 cashflowAverageApr = averageCashflowAPR(smoothingPeriod);

So the `updateDesiredAPR()` function will change the `targetAPR` using the smaller average value and the smoothing logic wouldn’t work as expected.

## Recommendation

```solidity
function _sendToDistributor(uint256 amount, uint256 epoch) internal {
  if (amount == 0) {
    state[epoch + 1].cumulativeCashflowApr = state[epoch].cumulativeCashflowApr + epochCashflowAPR(epoch);
    state[epoch + 1].cumulativeApr = state[epoch].cumulativeApr + epochAPR(epoch);
    state[epoch].bondedValue = bonding.averageBondedValue(epoch);

    return;
  }
```

I think `_sendToDistributor()` should update the cumulative `APR`s as well when `amount == 0`.

Interesting finding. It’s valid but the bug would actually result in the protocol retaining more capital due to reporting lower APRs than it should.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the reward throttling component that updates cumulative APR values across epochs. When the function that distributes overflow capital is called with a zero amount, it returns immediately without advancing the cumulativeCashflowApr and cumulativeApr fields for the next epoch. This omission occurs whenever the protocol experiences a gap between the stored activeEpoch and the current epoch reported by the timekeeper, and the overflow pool has no remaining balance for one or more of those intermediate epochs. Because the cumulative APRs are not incremented for those zero‑balance epochs, the average cash‑flow APR calculated later is artificially low. The contract then uses this understated average in the updateDesiredAPR routine, causing the targetAPR to be set lower than it should be. As a result the protocol appears to retain more capital than intended, and users see reduced reward rates or lower reported returns. The bug is triggered only when the active epoch is behind the current epoch by at least two periods and the overflow pool returns zero for the intervening epochs, a situation that can arise naturally if rewards are exhausted or if the system is paused. It was discovered during a manual audit that inspected the flow of checkRewardUnderflow and noticed that the comment flagged cumulative APR tracking as wrong for multi‑epoch gaps. The issue is subtle because the contract still transfers the correct amount of capital when it is available, and the missing APR update does not revert any state, making the discrepancy visible only in derived metrics such as cashflowAverageApr. From a user perspective the dashboard may show a sudden drop in APR, expected rewards may be lower than advertised, and the protocol’s smoothing logic may behave unexpectedly. The class of bug is an accounting omission in a cumulative metric update, similar to a missing step in a rolling‑window calculation. The proper fix is to ensure that the cumulative APR fields are updated even when the distributed amount is zero, for example by moving the APR update logic outside the amount‑zero guard or by explicitly handling the zero‑case to propagate the previous epoch’s values forward.
