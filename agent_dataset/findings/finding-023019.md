---
id: 23019
severity: "High"
---

# The _totalStaked tracker calculation is incor-

## Description

During debtWriteOff call in the UserManager, subtracting the amount instead of realAmount will lead to the whole gInflationIndex being inflated in the Comptroller contract, as well as general accounting inflation.
Due to the UserManager's _totalStaked being coupled with the Comptroller's gInflationIndex, the userInfo stake's inflationIndex will be calculated absolutely incorrectly:
```solidity
/**
*
*
*
*
*
*
*/
function _calculateRewardsInternal(
    address account,
    address token,
    uint256 totalStaked,
    UserManagerAccountState memory user
) internal view returns (uint256) {
    Info memory userInfo = users[account][token];
    uint256 startInflationIndex = userInfo.inflationIndex; // @@ <<< this internally depends on the UserManager's _totalStaked variable

    uint256 rewardMultiplier = _getRewardsMultiplier(user);
    uint256 curInflationIndex = _getInflationIndexNew(totalStaked, getTimestamp() - gLastUpdated);

    if (curInflationIndex < startInflationIndex) revert InflationIndexTooSmall();
    return userInfo.accrued + (curInflationIndex - startInflationIndex).wadMul(user.effectiveStaked).wadMul(rewardMultiplier);

}
68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/token/Comptroller.sol#L293)
```
Furthermore, during the reward accrual, there's another outcome of the miscalculated _totalStaked and gInflationIndex values:
```solidity
function _accrueRewards(address account, address token) private returns (uint256) {

    IUserManager userManager = _getUserManager(token);
    // Lookup global state from UserManager
    uint256 globalTotalStaked = userManager.globalTotalStaked(); // @@ <<< here a wrong _totalStaked amount is retrieved!!!

    // Lookup account state from UserManager
    UserManagerAccountState memory user = UserManagerAccountState(0, 0, false);
    (user.effectiveStaked, user.effectiveLocked, user.isMember) = userManager.onWithdrawRewards(account);

    uint256 amount = _calculateRewardsInternal(account, token, globalTotalStaked, user); // @@ <<< here a wrong amount is passed down to the calculation!

    // update the global states
    gInflationIndex = _getInflationIndexNew(globalTotalStaked, getTimestamp() - gLastUpdated);

    gLastUpdated = getTimestamp();
    users[account][token].inflationIndex = gInflationIndex;
    return amount;
}
udit/2024-06-union-finance-update-2/blob/7ffe43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/token/Comptroller.sol#L220C1-L238C6.
```
References for the main problem:
e43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/token/Comptroller.sol#L276
e43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/token/Comptroller.sol#L287
The culprit's details are further explained below.
This is due to using a non-scaled amount instead of the scaled realAmount in the-union-finance-update-2/blob/7ffe43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/user/UserManager.sol#L834
In this update Union Finance adds distinct definitions for the actualAmount being the real scaled token amount, and the amount being an unscaled nominal amount that is to be scaled by stakingTokenDecimal, and is usually accepted as an argument for functions within the UserManager contract.
Both stake and unstake functions track the totalStaked balance as a scaled AND 6-union-finance-update-2/blob/7ffe43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/user/UserManager.sol#L784. The snippet:
```solidity
function unstake(uint96 amount) external whenNotPaused nonReentrant {
    Staker storage staker = _stakers[msg.sender];
    // Stakers can only unstaked stake balance that is unlocked. Stake balance
    // becomes locked when it is used to underwrite a borrow.
    if (staker.stakedAmount - staker.locked < decimalScaling(amount, stakingTokenDecimal))

        revert InsufficientBalance();
    comptroller.withdrawRewards(msg.sender, stakingToken);
    uint256 remaining = IAssetManager(assetManager).withdraw(stakingToken, msg.sender, amount);

    if (remaining > amount) {
        revert AssetManagerWithdrawFailed();
    }
    uint96 actualAmount = decimalScaling(uint256(amount) - remaining, stakingTokenDecimal).toUint96();

    staker.stakedAmount -= actualAmount;
    _totalStaked -= actualAmount; // @@ <<< the actualAmount is subtracted
    emit LogUnstake(msg.sender, amount - remaining.toUint96());
}
```
on-finance-update-2/blob/7ffe43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/user/UserManager.sol#L748), correspondingly:
```solidity
function stake(uint96 amount) public whenNotPaused nonReentrant {
    IERC20Upgradeable erc20Token = IERC20Upgradeable(stakingToken);
    uint96 actualAmount = decimalScaling(uint256(amount), stakingTokenDecimal).toUint96();

    comptroller.withdrawRewards(msg.sender, stakingToken);
    Staker storage staker = _stakers[msg.sender];
    if (staker.stakedAmount + actualAmount > _maxStakeAmount) revert StakeLimitReached();

    staker.stakedAmount += actualAmount;
    _totalStaked += actualAmount; // @@ <<< here you can see it!
    erc20Token.safeTransferFrom(msg.sender, address(this), amount);
    uint256 currentAllowance = erc20Token.allowance(address(this), assetManager);
    if (currentAllowance < amount) {
        erc20Token.safeIncreaseAllowance(assetManager, amount - currentAllowance);

    }
    if (!IAssetManager(assetManager).deposit(stakingToken, amount)) revert AssetManagerDepositFailed();

    emit LogStake(msg.sender, amount);
}
```
However, the debtWriteOff function doesn't subtract the actualAmount, but decreases the _totalStaked counter by a non-scaled amount value:
```solidity
Staker storage staker = _stakers[stakerAddress];
staker.stakedAmount -= actualAmount.toUint96();
staker.locked -= actualAmount.toUint96();
staker.lastUpdated = currTime.toUint64();
_totalStaked -= amount;
// update vouch trust amount
vouch.trust -= actualAmount.toUint96();
vouch.locked -= actualAmount.toUint96();
vouch.lastUpdated = currTime.toUint64();
```
Then here later in the batchUpdateFrozenInfo function (that can be called by anyone and is unrestricted!), the Comptroller contract is notified of the new pdate-2/blob/7ffe43f68a1b8e8de1dfd9de5a4d89c90fd6f710/union-v2-contracts/contracts/user/UserManager.sol#L1121):
```solidity
comptroller.updateTotalStaked(stakingToken, _totalStaked - _totalFrozen);
}

function globalTotalStaked() external view returns (uint256 globalTotal) {
    globalTotal = _totalStaked - _totalFrozen;
}
```
The problem lies in this change here:
https://github.com/unioncredit/union-v2-contracts/pull/172/files#diff-e274f419b6384471f87c2b7d6a2c75150b95d37f3174a21d7d675ad20e3e4464R834
The Comptroller's updateTotalStaked function gets called:
```solidity
/**
*
*
*
*/
function updateTotalStaked(
    address token,
    uint256 totalStaked
) external override whenNotPaused onlyUserManager(token) returns (bool) {
    if (totalStaked > 0) {
        gInflationIndex = _getInflationIndexNew(totalStaked, getTimestamp() - gLastUpdated);

        gLastUpdated = getTimestamp();
    }
    return true;
}
```
And finally, the gInflationIndex value will be inflated.
Internal pre-conditions
1. As far as I can tell, the attack will be unintentional in most cases, happening automatically on each debtWriteOff call, because the culprit is an improper calculation.
2. Or this can be utilized together with calling batchUpdateFrozenInfo to inflate the gInflationIndex value intentionally and cause the Comptroller's _getInflationIndexNew to return incorrect results:
```solidity
gInflationIndex = _getInflationIndexNew(totalStaked, getTimestamp() - gLastUpdated);

```
External pre-conditions
None. The bug is just implicitly there.
Attack Path
As it's a mistake in the _totalStaked calculation logic, there's no particular trigger for this attack, as it will happen if any user write'sOffDebt.
The whole gInflationIndex will be inflated, and will be calculated incorrectly.
Besides that, tracking the wrong amount of the currently active staked tokens will be misleading for the external users that refer to that value.

## Proof of Concept

no poc

## Recommendation

Instead of subtracting amount, you should subtract the actualAmount from the _totalStaked variable here in writeOffDebt:
```solidity
Staker storage staker = _stakers[stakerAddress];
staker.stakedAmount -= actualAmount.toUint96();
staker.locked -= actualAmount.toUint96();
staker.lastUpdated = currTime.toUint64();
- _totalStaked -= amount;
+ _totalStaked -= actualAmount;
// update vouch trust amount
vouch.trust -= actualAmount.toUint96();
vouch.locked -= actualAmount.toUint96();
vouch.lastUpdated = currTime.toUint64();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mis‑calculation in the way the protocol tracks the total amount of tokens that are currently staked. The UserManager contract keeps a variable that records the aggregate staked balance in a scaled form (actualAmount). When a debt write‑off operation is performed, the code subtracts the unscaled nominal amount (amount) from this aggregate counter instead of the correctly scaled value (actualAmount). Because the aggregate counter is later used by the Comptroller contract to compute a global inflation index, the mismatch causes the inflation index to be artificially increased. This inflated index is then used in reward calculations, leading to rewards being over‑issued or, conversely, to users seeing their accrued rewards reduced unexpectedly. The bug manifests whenever any user triggers a debtWriteOff, and can be amplified by repeatedly calling the unrestricted batchUpdateFrozenInfo function, which forces the Comptroller to update its inflation index based on the corrupted total‑staked value. Affected parties include stakers, reward claimants, and any external system that relies on the reported total‑staked amount for accounting or risk assessment. The issue was discovered during a manual audit of the Union Finance v2 contracts, where the auditor noticed that the subtraction in debtWriteOff used the wrong variable and that the subsequent call to updateTotalStaked propagated the error. The problem is subtle because the contract still updates the per‑account staked balances correctly; only the global aggregate is wrong, so normal UI balances appear unchanged while the hidden inflation index diverges. The impact is high: an inflated inflation index can cause the protocol to mint excessive reward tokens, diluting existing holders, or can lead to accounting inconsistencies that break trust in the protocol’s financial statements. The bug belongs to the class of “incorrect scaling of accounting variables” or “global state mis‑alignment due to mixed units”. To remediate, the write‑off logic must subtract the scaled actualAmount from the total‑staked counter, ensuring both per‑account and global counters use the same unit. After fixing, the Comptroller’s inflation index will be calculated from a correct total‑staked value, restoring accurate reward accrual and preventing unintended inflation of token supplies.
