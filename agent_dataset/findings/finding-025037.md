---
id: 25037
severity: "Low/Info"
---

# Incorrect ERC4626ExceededMaxRedeem event on ManagedLeveragedVault.sol:: cancelWithdrawalIntent()

## Description



## Proof of Concept

## Vulnerability Detail

Full function:

```solidity
function cancelWithdrawalIntent(uint256 epoch, uint256 sharesToCancel, address receiver) external nonReentrant {
    /// @dev To be tested, but I think that between CUTOFF and CUTOFF - EPOCH (60 mins and 45 mins) before end, it can be canceled
    if (epoch < getWithdrawalRequestEpoch(block.timestamp)) revert CancelTooLate();

    ManagedLeveragedVaultStorage storage $ = _getManagedLeveragedVaultStorage();

    if ($.reports[epoch].reported) revert AlreadyReported();
    uint256 shares = $.reports[epoch].balanceOf[msg.sender];
    if (shares == 0) revert AmountZero();
    if (sharesToCancel > shares) revert ERC4626ExceededMaxRedeem(msg.sender, sharesToCancel, shares);

    $.reports[epoch].balanceOf[msg.sender] -= sharesToCancel;
    $.reports[epoch].totalShares -= sharesToCancel;

    _transfer(address(this), receiver, sharesToCancel);

    emit WithdrawalIntentCanceled(msg.sender, receiver, epoch, sharesToCancel);
}
```

It shows that `ERC4626ExceededMaxRedeem` is emitted with `msg.sender`, which is the `receiver`, not the `owner`.

## Impact

Incorrect event emission.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR331`](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR331%60>)

## Recommendation

Use another event.
