---
id: 21150
severity: "High"
---

# Division before multiplication could lead to users losing 50% in `WithdrawalQueue`

## Description

In the `_getAvailable()` function, the calculation performs division before multiplication, which could result in precision loss. The consequence is that users may not be able to withdraw the amount they should receive, leaving some funds locked in the `WithdrawalQueue`.
```solidity
// @audit division before multiplication
function _getAvailable(uint256 _tokenId) private view returns (uint256) {
    return getShares[_tokenId] * _getWithdrawablePerShare() - getWithdrawn[_tokenId]; 
}

/// @notice Get the amount that can be withdrawn per share.
function _getWithdrawablePerShare() private view returns (uint256) {
    return (_totalWithdrawn + _asset.balanceOf(address(this))) / getTotalShares;
}
```

## Proof of Concept

Consider the following scenario:
```solidity
getShares[_tokenId] = 1e8
getWithdrawn[_tokenId] = 0
_totalWithdrawn = 0
_asset.balanceOf(address(this)) = 1e9 (1000 USDC)
getTotalShares = 5e8 + 1
```
The current calculation will yield:
```solidity
_getWithdrawablePerShare() = 1e9 / (5e8 + 1) = 1
_getAvailable() = 1e8 * 1 - 0 = 1e8 = 100000000
```
However, the users should actually receive:
```solidity
getShares[_tokenId] * _asset.balanceOf(address(this)) / getTotalShares
= 1e8 * 1e9 / (5e8 + 1) = 199999999
```
As shown, the users lose almost 50% of what they should receive.

## Recommendation

Change the order of calculation to multiply before division.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision‑loss arithmetic error that occurs because the contract calculates the withdrawable amount per share by performing a division before a multiplication. In the private function that determines how much a token holder can withdraw, the code first computes (_totalWithdrawn + balance) / totalShares, which is an integer division that truncates any fractional part, and only afterwards multiplies the result by the holder’s share count. Since Solidity uses integer arithmetic, any remainder from the division is discarded, causing the subsequent multiplication to be based on a rounded‑down value. This ordering means that the amount returned by the function can be significantly lower than the mathematically correct proportional share of the contract’s assets. An attacker or any user can exploit this by holding a share amount that, when multiplied by the truncated per‑share value, yields far less than the expected payout. In the provided example, a holder with 1e8 shares should receive roughly 199,999,999 units of the asset, but because the division is performed first, the contract only returns 100,000,000 units – a loss of almost 50 %. The impact is that users may be unable to withdraw the full amount they are entitled to, effectively locking a portion of the protocol’s funds in the WithdrawalQueue. This condition manifests whenever the total number of shares does not divide evenly into the contract’s asset balance, which is a common situation in real‑world deployments where deposits and withdrawals happen asynchronously. All participants who rely on the withdrawal function – token holders, liquidity providers, and the protocol itself – are affected because the accounting assumptions that each share represents an exact fraction of the pool are violated. The issue was discovered during a formal audit when the auditors examined the arithmetic flow and identified the division‑before‑multiplication pattern as a source of rounding error. It can be hard to notice because the code appears to follow a logical sequence and the loss may only become evident with large share values or specific total‑share configurations, making the bug subtle in routine testing. From a user’s perspective the symptom is that a withdrawal transaction completes successfully but the received balance is far lower than expected, sometimes even zero, leading to confusion and loss of trust. The bug belongs to the class of rounding‑error or precision‑loss vulnerabilities that arise from improper ordering of integer arithmetic operations. To remediate the issue the calculation should be reordered so that the multiplication is performed before the division, i.e., (shares * (totalWithdrawn + balance)) / totalShares, or an alternative safe‑math library that preserves full precision should be used. This change restores the intended proportional distribution of assets and aligns the contract’s behavior with its economic model.
