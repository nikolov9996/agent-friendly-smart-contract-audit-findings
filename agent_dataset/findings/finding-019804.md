---
id: 19804
severity: "High"
---

# Staker can manipulate lockedCoinAge and earn extra rewards

## Description

Voucher can be counted arbitrary many times in staker's lockedCoinAge. If a voucher has maximized its trust then its locked is added to the lockedCoinAge each time fully as its lastUpdated is kept intact. This provides a surface to grow lockedCoinAge as big as an attacker wants, increasing it by current_block_difference * vouch.locked on each transaction.
vouch.lastUpdated is used for stakers[vouch.staker].lockedCoinAge accumulator and should be updated whenever its current state is recorded there. However, now it is not always the case as lockedCoinAge is updated in updateLocked() for every vouch until remaining is hit, while for the vouches, whose trust is maxxed in the borrow case (lock == true), such lastUpdated renewal doesn't take place.
An attacker will be able to steal all UNION rewards at once as with lockedCoinAge arbitrary big the reward multiplier, which isn't controlled to the upside, will be arbitrary big as well and an attacker will claim all available UNION in the contract.
updateLocked() accumulates stakers[vouch.staker].lockedCoinAge before vouch logic is run.
However, lastUpdated isn't always updated, which leads to ability to grow the accumulator when lock == true and vouch.trust == vouch.locked:
ontracts/user/UserManager.sol#L838-L870
```solidity
uint256 lastWithdrawRewards = getLastWithdrawRewards[vouch.staker];
stakers[vouch.staker].lockedCoinAge +=
    (block.number - _max(lastWithdrawRewards, uint256(vouch.lastUpdated))) *
    uint256(vouch.locked);
if (lock) {
    // Look up the staker and determine how much unlock stake they
    // have available for the borrower to borrow. If there is 0
    // then continue to the next voucher in the array
    uint96 stakerLocked = stakers[vouch.staker].locked;
    uint96 stakerStakedAmount = stakers[vouch.staker].stakedAmount;
    uint96 availableStake = stakerStakedAmount - stakerLocked;
    uint96 lockAmount = _min(availableStake, vouch.trust - vouch.locked);
    if (lockAmount == 0) continue;
    // Calculate the amount to add to the lock then
    // add the extra amount to lock to the stakers locked amount
    // and also update the vouches locked amount and lastUpdated block
    innerAmount = _min(remaining, lockAmount);
    stakers[vouch.staker].locked = stakerLocked + innerAmount;
    vouch.locked += innerAmount;
    vouch.lastUpdated = uint64(block.number);
} else {
    // Look up how much this vouch has locked. If it is 0 then
    // continue to the next voucher. Then calculate the amount to
    // unlock which is the min of the vouches lock and what is
    // remaining to unlock
    uint96 locked = vouch.locked;
    if (locked == 0) continue;
    innerAmount = _min(locked, remaining);
    // Update the stored locked values and last updated block
    stakers[vouch.staker].locked -= innerAmount;
    vouch.locked -= innerAmount;
    vouch.lastUpdated = uint64(block.number);
}
```
updateLocked( ..., true) is called on each borrow() with amount > minBorrow:
ontracts/market/UToken.sol#L525-L568
```solidity
function borrow(address to, uint256 amount) external override
    onlyMember(msg.sender) whenNotPaused nonReentrant {
    IAssetManager assetManagerContract = IAssetManager(assetManager);
    if (amount < minBorrow) revert AmountLessMinBorrow();
    if (amount > getRemainingDebtCeiling()) revert AmountExceedGlobalMax();
    // Call update locked on the userManager to lock this borrowers stakers. This function
    // will revert if the account does not have enough vouchers to cover the borrow amount. ie
    // the borrower is trying to borrow more than is able to be underwritten
    IUserManager(userManager).updateLocked(msg.sender, (actualAmount + fee).toUint96(), true);
```
So, whenever it's lock == true, vouch.trust == vouch.locked, the stakers[vouch.staker].lockedCoinAge += (block.number - _max(lastWithdrawRewards, uint256(vouch.lastUpdated))) * uint256(vouch.locked) will be counted for such a voucher with old vouch.lastUpdated as many times as updateLocked() run, which can be orchestrated easily enough.
Suppose Bob the staker has a vouch with trust maxxed, i.e. vouch.trust = vouch.locked = 10k DAI. He can setup a second borrower being his own account, some minimal trust, then can run min borrow many, many times, gaining huge stakers[vouch.staker].lockedCoinAge as vouch.lastUpdated aren't updated and lockedCoinAge grows with a positive some_number_of_blocks * 10k DAI number each time Bob borrows 1 DAI via his second borrower.
some_number_of_blocks here is (block.number - _max(lastWithdrawRewards, uint256(vouch.lastUpdated))) and it can be any as attack is viable as long as it is positive. Bob can wait for some time before proceeding to grow this number of blocks to make the attack bit more effective.
With effectiveLocked arbitrary big Bob will be able to obtain arbitrary big lendingRatio and _getRewardsMultiplier() result:
ontracts/token/Comptroller.sol#L433-L445
```solidity
function _getRewardsMultiplier(UserManagerAccountState memory user) internal pure returns (uint256) {
    if (user.isMember) {
        if (user.effectiveStaked == 0) {
            return memberRatio;
        }
        uint256 lendingRatio = user.effectiveLocked.wadDiv(user.effectiveStaked);
        return lendingRatio + memberRatio;
    } else {
        return nonMemberRatio;
    }
}
```
This will issue an arbitrary big amount of rewards to him, so Bob can effectively steal all UNION from the reward contract:
ontracts/token/Comptroller.sol#L341-L364
```solidity
function _calculateRewardsByBlocks(
    address account,
    address token,
    uint256 pastBlocks,
    Info memory userInfo,
    uint256 totalStaked,
    UserManagerAccountState memory user
) internal view returns (uint256) {
    uint256 startInflationIndex = users[account][token].inflationIndex;
    if (user.effectiveStaked == 0 || totalStaked == 0 || startInflationIndex == 0 || pastBlocks == 0) {
        return 0;
    }
    uint256 rewardMultiplier = _getRewardsMultiplier(user);
    uint256 curInflationIndex = _getInflationIndexNew(totalStaked, pastBlocks);
    if (curInflationIndex < startInflationIndex) revert InflationIndexTooSmall();
    return
        userInfo.accrued +
        (curInflationIndex - startInflationIndex).wadMul(user.effectiveStaked).wadMul(rewardMultiplier);
}
```

## Proof of Concept

no poc

## Recommendation

Consider updating vouch.lastUpdated every time it participated in lockedCoinAge accumulator:
ontracts/user/UserManager.sol#L838-L870
```solidity
uint256 lastWithdrawRewards = getLastWithdrawRewards[vouch.staker];
stakers[vouch.staker].lockedCoinAge +=
    (block.number - _max(lastWithdrawRewards, uint256(vouch.lastUpdated))) *
    uint256(vouch.locked);
vouch.lastUpdated = uint64(block.number);
if (lock) {
    // Look up the staker and determine how much unlock stake they
    // have available for the borrower to borrow. If there is 0
    // then continue to the next voucher in the array
    uint96 stakerLocked = stakers[vouch.staker].locked;
    uint96 stakerStakedAmount = stakers[vouch.staker].stakedAmount;
    uint96 availableStake = stakerStakedAmount - stakerLocked;
    uint96 lockAmount = _min(availableStake, vouch.trust - vouch.locked);
    if (lockAmount == 0) continue;
    // Calculate the amount to add to the lock then
    // add the extra amount to lock to the stakers locked amount
    // and also update the vouches locked amount and lastUpdated block
    innerAmount = _min(remaining, lockAmount);
    stakers[vouch.staker].locked = stakerLocked + innerAmount;
    vouch.locked += innerAmount;
} else {
    // Look up how much this vouch has locked. If it is 0 then
    // continue to the next voucher. Then calculate the amount to
    // unlock which is the min of the vouches lock and what is
    // remaining to unlock
    uint96 locked = vouch.locked;
    if (locked == 0) continue;
    innerAmount = _min(locked, remaining);
    // Update the stored locked values and last updated block
    stakers[vouch.staker].locked -= innerAmount;
    vouch.locked -= innerAmount;
}
```
It is used only in _getEffectiveAmounts() as an addition to coinAge.lockedCoinAge already recorded:
ontracts/user/UserManager.sol#L927-L929
```solidity
uint256 lastUpdateBlock = _max(coinAge.lastWithdrawRewards, uint256(vouch.lastUpdated));
coinAge.lockedCoinAge += (block.number - lastUpdateBlock) * locked;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic manipulation of the lockedCoinAge accumulator used to compute reward multipliers for stakers. The root cause is that the timestamp field vouch.lastUpdated, which should be refreshed each time the voucher contributes to the lockedCoinAge total, is only updated in the unlock path and not when the lock flag is true and the voucher’s trust value is already fully locked (vouch.trust == vouch.locked). Because updateLocked adds (block.number‑_max(lastWithdrawRewards, vouch.lastUpdated)) * vouch.locked to stakers[vouch.staker].lockedCoinAge before the voucher logic runs, a malicious staker can repeatedly trigger updateLocked with lock==true while keeping vouch.lastUpdated unchanged. Each call therefore re‑adds the same block‑difference multiplied by the locked amount, allowing the attacker to grow lockedCoinAge to an arbitrarily large value simply by performing many small borrow transactions. The inflated lockedCoinAge inflates the lendingRatio used in _getRewardsMultiplier, which in turn multiplies the reward calculation, enabling the attacker to claim an arbitrarily large amount of UNION tokens – effectively draining the entire reward pool. The exploit is viable whenever a voucher’s trust is fully locked, the borrower calls borrow() with an amount above the minimum threshold, and the contract’s updateLocked function is invoked with the lock flag set to true. The affected parties include legitimate stakers who lose their expected rewards, borrowers who may see reduced incentives, and any token holder relying on the integrity of the reward distribution. The issue was discovered during a manual audit of the UserManager.updateLocked logic, where the missing vouch.lastUpdated assignment was identified as a logical flaw. It is hard to notice because the lockedCoinAge variable normally grows over time, so the extra increments appear as a natural increase rather than a malicious one. The recommended fix is to always assign vouch.lastUpdated = block.number after the lockedCoinAge accumulation, regardless of the lock flag, ensuring that each block interval is counted only once and preventing the accumulator from being artificially inflated. Conceptually, the bug belongs to the class of “state‑update omission” leading to unbounded reward multiplier escalation, violating the protocol’s accounting assumptions that rewards are proportional to genuine locked stake over time.
