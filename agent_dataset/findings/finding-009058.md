---
id: 9058
severity: "High"
---

# Broken accounting when cancelUnwinding is called one epoch after startUnwinding

## Description

When a user calls startUnwinding the positions mapping is updated as:
```solidity
positions[id] = UnwindingPosition({
    shares: newShares,
    fromEpoch: nextEpoch,
    toEpoch: endEpoch,
    fromRewardWeight: rewardWeight,
    rewardWeightDecrease: rewardWeightDecrease
});
```
For example, if a user calls startUnwinding in epoch 1000 with 10 as _unwindingEpochs, the positions mapping would be created as:
```solidity
positions[id] = UnwindingPosition({
    shares: newShares,
    fromEpoch: 1001,
    toEpoch: 1011,
    fromRewardWeight: rewardWeight,
    rewardWeightDecrease: rewardWeightDecrease
});
```
Moreover, these 2 mappings would also be updated:
```solidity
rewardWeightDecreases[1001] += rewardWeightDecrease;
rewardWeightIncreases[1011] += rewardWeightDecrease;
```
Then, once in the epoch 1001, this user would be able to call cancelUnwinding as this require check would pass:
```solidity
// currentEpoch = 1001
// position.fromEpoch = 1001
require(currentEpoch >= position.fromEpoch, UserUnwindingNotStarted());
```
cancelUnwinding would execute the following logic:
```solidity
function cancelUnwinding(address _user, uint256 _startUnwindingTimestamp, uint32 _newUnwindingEpochs)
external
onlyCoreRole(CoreRoles.LOCKED_TOKEN_MANAGER)
{
    uint32 currentEpoch = uint32(block.timestamp.epoch());
    bytes32 id = _unwindingId(_user, _startUnwindingTimestamp);
    UnwindingPosition memory position = positions[id];
    require(position.toEpoch > 0 && currentEpoch < position.toEpoch, UserNotUnwinding());
    require(currentEpoch >= position.fromEpoch, UserUnwindingNotStarted());
    uint256 userBalance = balanceOf(_user, _startUnwindingTimestamp);
    uint256 elapsedEpochs = currentEpoch - position.fromEpoch;
    uint256 userRewardWeight = position.fromRewardWeight - elapsedEpochs *
    position.rewardWeightDecrease;
    {
        // scope some state writing to avoid stack too deep
        GlobalPoint memory point = _getLastGlobalPoint();
        point.totalRewardWeightDecrease -= position.rewardWeightDecrease;
        point.totalRewardWeight -= userRewardWeight;
        _updateGlobalPoint(point);
        rewardWeightIncreases[position.toEpoch] -= position.rewardWeightDecrease;
        delete positions[id];
        totalShares -= position.shares;
        totalReceiptTokens -= userBalance;
    }
    uint32 remainingEpochs = position.toEpoch - currentEpoch;
    require(_newUnwindingEpochs >= remainingEpochs, InvalidUnwindingEpochs(_newUnwindingEpochs));
    IERC20(receiptToken).approve(msg.sender, userBalance);
    LockingController(msg.sender).createPosition(userBalance, _newUnwindingEpochs, _user);
}
```
Where _getLastGlobalPoint would iterate over previous epochs excluding the currentEpoch, which is where the rewardWeightDecreases[1001] += rewardWeightDecrease update was performed:
```solidity
function _getLastGlobalPoint() internal view returns (GlobalPoint memory) {
    GlobalPoint memory point = globalPoints[lastGlobalPointEpoch];
    // apply slope changes
    uint32 currentEpoch = uint32(block.timestamp.epoch());
    for (uint32 epoch = point.epoch; epoch < currentEpoch; epoch++) {
        point.totalRewardWeightDecrease -= rewardWeightIncreases[epoch];
        point.totalRewardWeightDecrease += rewardWeightDecreases[epoch];
        point.totalRewardWeight -= point.totalRewardWeightDecrease;
        point.epoch = epoch + 1;
        point.rewardShares = 0;
    }
    return point;
}
```
Despite that, cancelUnwinding still performs the following update, incorrectly pushing this update into the global point:
```solidity
GlobalPoint memory point = _getLastGlobalPoint();
point.totalRewardWeightDecrease -= position.rewardWeightDecrease;
```
At this point:
1. totalRewardWeightDecrease is higher than it should as the counter-part of this update (rewardWeightDecreases[1001]) was not yet processed.
2. Consequently, totalRewardWeight is lower than it should.
3. This error is written permanently into the global point here: _updateGlobalPoint(point).
Therefore, as the slope data is left in an inconsistent state forcing an incorrect totalRewardWeight distribution for everyone else in the UnwindingModule, users which balance is affected by this slope, will receive a higher amount of receipt tokens than they should.
Another consequence is that this would cause a DoS of the InfiniFi protocol as the UnwindingModule.totalRewardWeight calls would revert due to underflow in the following line:
```solidity
point.totalRewardWeightDecrease -= rewardWeightIncreases[epoch];
```

## Proof of Concept

no poc

## Recommendation

Consider updating the cancelUnwinding function require check to disallow users from cancelling when currentEpoch is equal to position.fromEpoch:
```solidity
require(currentEpoch > position.fromEpoch, UserUnwindingNotStarted());
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting inconsistency in the UnwindingModule that occurs when a user calls cancelUnwinding in the same epoch that the unwinding period starts. When startUnwinding is executed, the contract records a reward weight decrease for the upcoming epoch (rewardWeightDecreases[fromEpoch]) and a matching increase for the ending epoch (rewardWeightIncreases[toEpoch]). The cancelUnwinding function retrieves the latest global accounting point via _getLastGlobalPoint, which iterates over epochs strictly before the current one, therefore it does not apply the rewardWeightDecrease that was just recorded for the current epoch. After obtaining this point, cancelUnwinding subtracts position.rewardWeightDecrease a second time (point.totalRewardWeightDecrease -= position.rewardWeightDecrease). Because the decrease for the current epoch has not yet been incorporated, this subtraction double‑counts the decrease, leaving totalRewardWeightDecrease inflated and totalRewardWeight deflated. The erroneous values are then written back with _updateGlobalPoint, permanently corrupting the slope data used for reward distribution. As a result, the protocol distributes more receipt tokens than it should to users whose balances are affected by the slope, effectively creating a “funds disappear” scenario for the protocol and an over‑issuance for the attacker. Moreover, the corrupted slope can later cause an underflow when the contract processes rewardWeightIncreases in subsequent epochs, leading to a denial‑of‑service where UnwindingModule.totalRewardWeight reverts. The bug is triggered only when cancelUnwinding is called in the epoch immediately after startUnwinding (currentEpoch == position.fromEpoch) and the require checks allow it (require(currentEpoch >= position.fromEpoch)). Any user who initiates an unwinding and then cancels early can exploit the mis‑calculation, while all other participants suffer from incorrect reward accounting. The issue was discovered during a security audit by Spearbit, which traced the logic of reward weight updates and identified the double subtraction as a logical flaw. It is hard to notice because the accounting error does not manifest in normal operation; it appears only under the specific timing condition and the corrupted global point is not obvious without deep inspection of the slope handling code. The recommended mitigation is to tighten the require condition so that cancelUnwinding can only be called after the unwinding has actually progressed (require(currentEpoch > position.fromEpoch)), or to adjust the accounting logic to correctly account for the rewardWeightDecrease of the current epoch before applying the subtraction. This would restore proper reward weight tracking, prevent over‑issuance of receipt tokens, and avoid the potential underflow‑induced DoS.
