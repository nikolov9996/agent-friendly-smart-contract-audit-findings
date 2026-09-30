---
id: 4741
severity: "High"
---

# Attacker can take advantage of multiplier when there's only one second left, allowing them to fraudulently gain voting power Submitted by 0xRajkumar

## Description

In the main stake function, we have a require statement that checks whether our duration_ should be equal to zero or greater than or equal to _minDuration:
```solidity
require(
    duration_ == 0 || duration_ >= _minDuration,
    "duration too small"
);
```
But we are not checking this in calMintStakingPower when we have some remaining duration left because we are only checking if rd is greater than zero. This consideration assumes lockTime_ is zero and our lockAmount_ is greater than zero because we are staking lockAmount_ for rd time for our attack:

```solidity
function calMintStakingPower(
    LLocker.SLock memory oldLockData,
    uint lockAmount_,
    uint lockTime_,
    bool isSelfStake_,
    uint selfStakeAdvantage_
) internal view returns (uint) {
    uint rd = LLocker.restDuration(oldLockData);
    uint oldALock = oldLockData.amount;
    uint dLockForOldA = lockTime_;
    uint dLockForStakeA = lockTime_ + rd;
    if (lockTime_ == 0) {
        require(rd > 0, "already unlocked");
    }
    uint rs = (oldALock *
        calMultiplierForOldAmount(dLockForOldA) +
        lockAmount_ *
        calMultiplier(dLockForStakeA)) / LPercentage.DEMI;
    if (isSelfStake_) {
        rs = (rs * selfStakeAdvantage_) / LPercentage.DEMI;
    }
    return rs;
}
```
Now, attackers can take advantage of this to win the voting and earn Geth from whichever side they want.

Let's say someone has staked _minStakeDCTAmount for one month. When the remaining duration is very small, they can take advantage of this. Basically, if we consider the remaining duration to be 1 second, then our multiplier will be 0.88.

So, essentially, they can use any amount they want to lock for only 1 second and use the powerMinted to vote on 'voteId'.

Now let's take an example: An attacker has staked 7 Goat tokens for one month because it will be the minimum required amount. There is a voting going on with voting ID. The attacker can take a loan of a large amount of Goat tokens at the last second when the remaining duration is 1 second. They will stake it to receive dP2PDToken tokens, then proceed to vote on some voteIDs. After that, they will call lockWithdraw function with isForced function set to true, and then repay their loan with a fee. Because they're withdrawing with isForced equal to true, they will need to bear a little loss since they will be withdrawing 1 second early. However, if their earnings from votes can exceed the loss of the fee and penalty for withdrawing 1 second early, an attacker can plan this type of attack on a large scale.

If the minStakeAmount is much less, it will be very easy for him to perform this attack.

Let's say the attacker has taken a loan of 100 Goat, and he's staking for when the remaining duration is 1 second, then powerMinted is 88. After the attack, he can withdraw the same amount using the formula below, considering FS is 10000 then the duration will be 1 month because we staked 7 Goat for 1 month in starting.

Total will be 100 Goat, duration will be 1 month, and pastTime will be 1 month - 1 because the rest duration is 1 second.

Our receivedA in wei will be 99999961419753086419 with a loss of 38580246913581 wei. Now let's say the fees were 0.01, then the total loss will be 10000000000000000 + 38580246913581 = 10038580246913581 wei. The attacker can only perform the attack if he earns more than 10038580246913581 wei.

```solidity
function calDuration(
    SLock memory lockData_,
    uint fs_,
    bool isPoolOwner_
) internal pure returns (uint) {
    uint mFactor = isPoolOwner_ ? 2 * LPercentage.DEMI - fs_ : fs_;
    uint duration = (lockData_.duration * mFactor) / LPercentage.DEMI;
    return duration;
}
uint receivedA = (total * pastTime) / duration;
```

## Proof of Concept

no poc

## Recommendation

My recommendation is that we should check not only if rd is greater than zero, but also if it is significantly greater than 1 week or more, so that this type of attack will be very expensive and infeasible due to the penalty.
```solidity
function calMintStakingPower(
    LLocker.SLock memory oldLockData,
    uint lockAmount_,
    uint lockTime_,
    bool isSelfStake_,
    uint selfStakeAdvantage_
) internal view returns (uint) {
    uint rd = LLocker.restDuration(oldLockData);
    uint oldALock = oldLockData.amount;
    uint dLockForOldA = lockTime_;
    uint dLockForStakeA = lockTime_ + rd;
    if (lockTime_ == 0) {
        require(rd > 1 weeks, "already unlocked"); //-> Here
    }
    uint rs = (oldALock *
        calMultiplierForOldAmount(dLockForOldA) +
        lockAmount_ *
        calMultiplier(dLockForStakeA)) / LPercentage.DEMI;
    if (isSelfStake_) {
        rs = (rs * selfStakeAdvantage_) / LPercentage.DEMI;
    }
    return rs;
}
```
Check out this reference.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains a logic flaw in the calculation of staking power that allows an attacker to obtain an outsized amount of voting power by staking a large amount of tokens for an extremely short remaining lock duration. The function that mints staking power checks only that the remaining duration (rd) of an existing lock is greater than zero when the new lock time (lockTime_) is zero, but it does not enforce a minimum remaining duration. Because the multiplier used to compute voting power is based on the sum of the new lock time and the remaining duration, an attacker can wait until the existing lock has only one second left, then call the staking function with lockTime_ set to zero. The multiplier for a one‑second remaining duration is still relatively high (approximately 0.88), so the attacker receives a large amount of minted power for a negligible amount of time. The attacker can then use this inflated power to vote on governance proposals and earn reward tokens, after which they withdraw the staked tokens using a forced‑withdraw flag that incurs only a small penalty for the one‑second early exit. If the reward earned from the vote exceeds the penalty and any loan fee, the attacker profits, effectively buying voting influence for a fraction of the cost. This vulnerability manifests only when there is an existing lock with a very small remaining duration and the contract permits staking with lockTime_ equal to zero. Any user who can obtain a short‑term loan of tokens can exploit the bug, compromising the integrity of the governance process and allowing disproportionate reward extraction. The issue was discovered during a manual audit that noticed the missing duration check in calMintStakingPower. It is hard to notice because the require statement appears to protect against unlocking already expired locks, yet it does not guard against the edge case of a near‑expired lock, and the multiplier formula seems reasonable for normal durations. The bug belongs to the class of “insufficient input validation leading to economic manipulation” and violates the protocol’s assumption that voting power is proportional to the amount and length of a lock. From a user’s perspective the symptoms are unexpected spikes in voting weight when staking a token amount for only a second, and the ability to withdraw almost immediately with only a tiny loss. The contract should enforce that the remaining duration used in the multiplier calculation is above a safe threshold (for example, greater than one week) or redesign the multiplier to depend solely on the new lock time, thereby preventing the exploitation of near‑expired locks.
