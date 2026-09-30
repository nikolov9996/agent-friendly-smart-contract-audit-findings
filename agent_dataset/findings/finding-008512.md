---
id: 8512
severity: "High"
---

# User rewards stop accruing after any `_writeCheckpoint` calling action

## Description

Any user balance affecting action, i.e. deposit, withdraw/withdrawToken or getReward, calls _writeCheckpoint to update the balance records used for the earned reward estimation. The issue is that _writeCheckpoint always sets false to `voted` flag for the each new checkpoint due to wrong index used in the mapping access, while only voted periods are eligible for accruing the rewards.

This way any balance changing action of a voted user will lead to stopping of the rewards accrual for the user, until next vote will be cast. I.e. any action that has no relation to voting and should have only balance change as the reward accruing process impact, in fact removes any future rewards from the user until the next vote.

Setting the severity to be high as the impact here violates system logic and means next periods accrued rewards loss for a user.

## Proof of Concept

_writeCheckpoint adds a new checkpoint if block.timestamp is not found in the last checkpoint:

[Gauge.sol#L302-L313](https://github.com/code-423n4/2022-05-velodrome/blob/7fda97c570b758bbfa7dd6724a336c43d4041740/contracts/contracts/Gauge.sol#L302-L313)  

```solidity
function _writeCheckpoint(address account, uint balance) internal {
    uint _timestamp = block.timestamp;
    uint _nCheckPoints = numCheckpoints[account];

    if (_nCheckPoints > 0 && checkpoints[account][_nCheckPoints - 1].timestamp == _timestamp) {
        checkpoints[account][_nCheckPoints - 1].balanceOf = balance;
    } else {
        bool prevVoteStatus = (_nCheckPoints > 0) ? checkpoints[account][_nCheckPoints].voted : false;
        checkpoints[account][_nCheckPoints] = Checkpoint(_timestamp, balance, prevVoteStatus);
        numCheckpoints[account] = _nCheckPoints + 1;
    }
}
```

However, instead of moving vote status from the previous checkpoint it records `false` to `prevVoteStatus` all the time as last status is `checkpoints[account][_nCheckPoints-1].voted`, while `checkpoints[account][_nCheckPoints]` isn’t created yet and is empty:

[Gauge.sol#L309](https://github.com/code-423n4/2022-05-velodrome/blob/7fda97c570b758bbfa7dd6724a336c43d4041740/contracts/contracts/Gauge.sol#L309)  

```solidity
bool prevVoteStatus = (_nCheckPoints > 0) ? checkpoints[account][_nCheckPoints].voted : false;
```

Notice that `checkpoints` is a mapping and no range check violation happens:

[Gauge.sol#L74-L75](https://github.com/code-423n4/2022-05-velodrome/blob/7fda97c570b758bbfa7dd6724a336c43d4041740/contracts/contracts/Gauge.sol#L74-L75)  

```solidity
/// @notice A record of balance checkpoints for each account, by index
mapping (address => mapping (uint => Checkpoint)) public checkpoints;
```

This will effectively lead to rewards removal on any user action, as earned() used in rewards estimation counts only voted periods:

[Gauge.sol#L483-L502](https://github.com/code-423n4/2022-05-velodrome/blob/7fda97c570b758bbfa7dd6724a336c43d4041740/contracts/contracts/Gauge.sol#L483-L502)  

```solidity
if (_endIndex > 0) {
    for (uint i = _startIndex; i < _endIndex; i++) {
        Checkpoint memory cp0 = checkpoints[account][i];
        Checkpoint memory cp1 = checkpoints[account][i+1];
        (uint _rewardPerTokenStored0,) = getPriorRewardPerToken(token, cp0.timestamp);
        (uint _rewardPerTokenStored1,) = getPriorRewardPerToken(token, cp1.timestamp);
        if (cp0.voted) {
            reward += cp0.balanceOf * (_rewardPerTokenStored1 - _rewardPerTokenStored0) / PRECISION;
        }
    }
}

Checkpoint memory cp = checkpoints[account][_endIndex];
uint lastCpWeeksVoteEnd = cp.timestamp - (cp.timestamp % (7 days)) + BRIBE_LAG + DURATION;
if (block.timestamp > lastCpWeeksVoteEnd) {
    (uint _rewardPerTokenStored,) = getPriorRewardPerToken(token, cp.timestamp);
    if (cp.voted) {
        reward += cp.balanceOf * (rewardPerToken(token) - Math.max(_rewardPerTokenStored, userRewardPerTokenStored[token][account])) / PRECISION;
    }
}
```

I.e. if a user has voted, then performed any of the operations that call _writeCheckpoint update: deposit, withdraw/withdrawToken or getReward, then this user will not have any rewards for the period between this operation and the next vote as all checkpoints that were created by _writeCheckpoint will have `voted == false`.

## Recommendation

Update the index to be `_nCheckPoints-1`:

    -	bool prevVoteStatus = (_nCheckPoints > 0) ? checkpoints[account][_nCheckPoints].voted : false;
    +	bool prevVoteStatus = (_nCheckPoints > 0) ? checkpoints[account][_nCheckPoints - 1].voted : false;

Due to 1 typo / oversight in the line `bool prevVoteStatus = (_nCheckPoints > 0) ? checkpoints[account][_nCheckPoints].voted : false;` All future checkpoints are registered as having `voted` set to false.

Due to a configuration choice (or mistake as detailed in other findings), having `voted` set to false causes all rewards to not be receiveable.

While the impact is loss of Yield (typically a medium finding), the finding shows how this bug will systematically impact all gauges for all users.

Because of that, I believe High Severity to be appropriate.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one error in the checkpoint‑writing routine of the gauge contract that incorrectly records the voting status for newly created balance checkpoints. When a user who has previously voted performs any balance‑affecting operation – such as depositing more tokens, withdrawing, or claiming rewards – the internal function _writeCheckpoint creates a new checkpoint. Because the code reads the voted flag from checkpoints[account][_nCheckPoints] instead of the last existing checkpoint at checkpoints[account][_nCheckPoints‑1], the newly stored checkpoint always receives a voted flag of false. The reward‑calculation logic later iterates over checkpoints and only credits rewards for periods where the checkpoint’s voted flag is true. Consequently, any checkpoint created after the balance change is treated as a non‑voted period, causing the contract to skip reward accrual for the entire interval until the user casts another vote. From the user’s point of view, expected rewards disappear: after a deposit or withdrawal the UI may show a sudden drop to zero pending rewards, even though the user’s voting status has not changed. This mismatch violates the protocol’s economic model, which assumes that rewards continue to accrue for voted users regardless of ordinary balance updates. The issue was discovered during a formal audit when the reviewers examined the _writeCheckpoint implementation and observed that the vote status was never carried over to the new checkpoint. It can be hard to notice because the balance updates succeed and no explicit error is thrown; the symptom is simply a loss of expected yield. The flaw belongs to the class of checkpoint‑state mis‑assignment bugs, where an incorrect index or missing range check leads to wrong flag propagation, breaking downstream accounting logic. To remediate, the code should retrieve the previous checkpoint’s voted flag using the index _nCheckPoints‑1, ensuring that the new checkpoint inherits the correct voting status. This change restores proper reward accrual for all periods between balance‑changing actions, aligning contract behavior with the intended incentive design.
