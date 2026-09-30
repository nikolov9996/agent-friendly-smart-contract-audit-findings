---
id: 4731
severity: "High"
---

# When stake eth in earningreinvest, the reduction of maxearning may not work Submitted by cccz

## Description

In order to incentivize users to stake the ETH earnings in earningReinvest, maxEarning is reduced to keep the ﬁnancial stability.
```solidity
function earningReinvest(
    bool isEth_,
    address payable poolOwner_,
    uint duration_,
    uint amount_,
    // address[] memory pulledPoolOwners_,
    uint minSPercent_,
    uint poolConfigCode_
)
external
{
    address account = msg.sender;
    if (isEth_) {
        LLocker.SLock memory oldLockData = _eLocker.getLockData(account, poolOwner_);
        uint realDuration = duration_ + LLocker.restDuration(oldLockData);
        if (realDuration > _maxDuration) {
            realDuration = _maxDuration;
        }
        uint maxEarning = _eEarning.maxEarningOf(account);
        maxEarning -= amount_ * realDuration / _maxDuration;
        _eEarning.updateMaxEarning(account, maxEarning);
    }
    earningWithdraw(isEth_, amount_, payable(address(this)), 0);
    _stake(isEth_, account, poolOwner_, duration_, minSPercent_, poolConfigCode_);
}
```
However, since earning.withdraw calls shareCommission, which updates maxEarning, the previous reduction of maxEarning will not work.
```solidity
function earningWithdraw(
    bool isEth_,
    uint amount_,
    address payable dest_,
    uint minEthA_
    // address[] memory pulledPoolOwners_
)
public
{
    address account = msg.sender;
    // earningPulls(account, pulledPoolOwners_, account);
    IEarning earning = isEth_ ? _eEarning : _dEarning;
    earning.withdraw(account, amount_, address(this));
    // ...
}
function withdraw(
    address account_,
    uint amount_,
    address dest_
)
external
onlyAdmin
{
    shareCommission(account_);
    // ...
    if (_sharedA[account_] > _maxEarningOf[account_]) {
        _updateMaxEarning(account_, _sharedA[account_]);
    }
}
```
Consider maxEarning = 1000, _sharedA = 1000, balanceOf = 1100 (100 no shareCommission, sPercent=10%), fs = 1. The user earningReinvest 1000 with maxDuration, and maxEarning is reduced to 0. However, when earning.withdraw calls shareCommission, _sharedA is updated to 1000 + 100 * 0.9 = 1090, and _maxEarningOf changes from 0 to 1090. At the end of _stake, fs = ((1090 - 1000) + 1000 * 2%) / 1090 = 0.1, this reduces the poolOwner's score to 1/10.

## Proof of Concept

no poc

## Recommendation

The ﬁx will be to reduce maxEarning after withdraw:
```solidity
function earningReinvest(
    bool isEth_,
    address payable poolOwner_,
    uint duration_,
    uint amount_,
    // address[] memory pulledPoolOwners_,
    uint minSPercent_,
    uint poolConfigCode_
)
external
{
    address account = msg.sender;
    earningWithdraw(isEth_, amount_, payable(address(this)), 0);
    if (isEth_) {
        LLocker.SLock memory oldLockData = _eLocker.getLockData(account, poolOwner_);
        uint realDuration = duration_ + LLocker.restDuration(oldLockData);
        if (realDuration > _maxDuration) {
            realDuration = _maxDuration;
        }
        uint maxEarning = _eEarning.maxEarningOf(account);
        maxEarning -= amount_ * realDuration / _maxDuration;
        _eEarning.updateMaxEarning(account, maxEarning);
    }
    _stake(isEth_, account, poolOwner_, duration_, minSPercent_, poolConfigCode_);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect ordering of state updates in the earningReinvest workflow of the protocol. When a user stakes ETH earnings through earningReinvest, the function first reads the current maxEarning value for the caller, calculates a reduction proportional to the amount being reinvested and the effective lock duration, and writes the reduced value back to the earnings contract. The intention of this reduction is to preserve financial stability by limiting the maximum future earnings a user can claim. However, immediately after this reduction the function invokes earningWithdraw, which internally calls shareCommission. The shareCommission routine updates the shared amount (_sharedA) and, if the shared amount exceeds the stored maxEarning, it calls _updateMaxEarning to raise maxEarning to the new shared total. Because shareCommission runs after the manual reduction, it overwrites the reduced maxEarning with a larger value derived from the commission calculation. Consequently, the intended reduction is effectively cancelled. This flaw manifests when a user calls earningReinvest with ETH, supplies an amount equal to or close to their current maxEarning, and uses the maximum allowed lock duration. Under these conditions the protocol records a temporary maxEarning of zero, but the subsequent withdraw restores it to a value higher than zero (for example 1090 in the illustrated scenario). The restored maxEarning is then used in the staking logic to compute the poolOwner’s score (fs), leading to an unexpectedly low score (e.g., 0.1) and an inaccurate representation of the pool’s health. From a user perspective the symptoms are subtle: the UI may show that the reinvestment succeeded, but the poolOwner’s reputation or reward multiplier drops dramatically without an obvious cause, and the accounting numbers no longer match the expected financial model. The issue was discovered during a manual audit by Spearbit, who noticed that the maxEarning reduction appeared to have no lasting effect. It is hard to detect because the contract does not emit explicit events for the intermediate reduction, and the final state after the withdraw looks plausible, masking the logical inconsistency. The bug belongs to the class of state‑invalidation or ordering bugs where a later internal call unintentionally reverts a prior state change. To remediate the problem the reduction of maxEarning must be performed after the withdraw (or the withdraw must be modified not to adjust maxEarning), ensuring that the final stored maxEarning reflects the intended lower bound. This change restores the accounting invariants, prevents unintended score reductions, and preserves the protocol’s financial stability guarantees.
