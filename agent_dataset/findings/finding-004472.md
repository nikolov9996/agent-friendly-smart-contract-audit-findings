---
id: 4472
severity: "Medium"
---

# Attacker can make restricted calls from any wallet

## Description

When value is 0 in spend(), it no longer checks whether permission is approved and will make restricted calls from the wallet. In spend(), it first calls _useSpendPermission() to consume the allowances, and then calls _transferFrom() to perform the asset transfer on the wallet:
```solidity
function spend(SpendPermission memory spendPermission, address recipient, uint160 value)
public
requireSender(spendPermission.spender)
{
    _useSpendPermission(spendPermission, value);
    _transferFrom(spendPermission.account, spendPermission.token, recipient, value);
}
```
And in _useSpendPermission(), it calls isApproved() to check whether the permission is approved.
```solidity
function _useSpendPermission(SpendPermission memory spendPermission, uint256 value) internal {
    // early return if no value spent
    if (value == 0) return;
    // require spend permission is approved and not revoked
    if (!isApproved(spendPermission)) revert UnauthorizedSpendPermission();
```
The problem is that it skips the isApproved() check when the value is 0, so an attacker can make the call from any wallet with unapproved permissions. Then in _transferFrom(), since value = 0, the attacker cannot steal any assets:
```solidity
function _transferFrom(address account, address token, address recipient, uint256 value) internal {
    // transfer tokens from account to recipient
    if (token == NATIVE_TOKEN) {
        _execute({account: account, target: recipient, value: value, data: hex""});
    } else {
        _execute({
            account: account,
            target: token,
            value: 0,
            data: abi.encodeWithSelector(IERC20.transfer.selector, recipient, value)
        });
    }
}
```
However, as a special case, the early ERC721 standard has the transfer(address _to, uint _tokenId) interface, and cryptoKitties supports it, so if the wallet has cryptoKitties#0, the attacker can steal it.
```solidity
function transfer(
    address _to,
    uint256 _tokenId
)
external
whenNotPaused
{
```

## Proof of Concept

```solidity
Add MockRecipient contract:
pragma solidity ^0.8.23;
contract MockRecipient {
    address public caller;
    fallback () external payable {
        caller = msg.sender;
    }
}
```
And add the following test to spend.t.sol:
```solidity
function test_poc() public {
    uint48 start = 1000;
    address spender = address(0xb0b);
    SpendPermissionManager.SpendPermission memory spendPermission = SpendPermissionManager.SpendPermission({
        account: address(account),
        spender: spender,
        token: NATIVE_TOKEN,
        start: start,
        end: uint48(start+1000),
        period: 200,
        allowance: 1e18
    });
    vm.warp(start);
    vm.startPrank(spender);
    mockSpendPermissionManager.spend(spendPermission, address(recipient), 0);
    vm.stopPrank();
    assert(recipient.caller() == address(account));
}
```
Run the test, an attacker can use unapproved permissions to call the fallback function of an arbitrary contract.

## Recommendation

Move the isApproved() check to the front:
```solidity
function _useSpendPermission(SpendPermission memory spendPermission, uint256 value) internal {
    // require spend permission is approved and not revoked
    if (!isApproved(spendPermission)) revert UnauthorizedSpendPermission();
    // early return if no value spent
    if (value == 0) return;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization bypass that occurs when the spend() function is invoked with a transfer amount of zero. In the normal flow, spend() first calls an internal helper _useSpendPermission() which checks that the supplied SpendPermission object has been approved via isApproved(). However, _useSpendPermission() contains an early‑return clause that exits immediately if the value argument equals zero, and the approval check is placed after this clause. As a result, when value is zero the contract skips the isApproved() verification entirely and proceeds to call _transferFrom() with a zero amount. Although a zero ERC20 transfer does not move any tokens, the _transferFrom() implementation still performs an external call to the recipient address (or to the token contract for ERC20) and, for ERC721 tokens that follow the older transfer(address,uint256) signature such as CryptoKitties, the call can trigger a legitimate token transfer even when the amount parameter is zero. Consequently, an attacker can craft a SpendPermission that references a wallet they do not control, set the value to zero, and invoke spend() from any address. The contract will then execute the fallback function of an arbitrary contract or, in the special case of an ERC721 with a transfer function that does not require a non‑zero amount, transfer ownership of the NFT to the attacker. The impact is that the permission model of the wallet is broken: unauthorized parties can cause the wallet to interact with external contracts, potentially stealing NFTs or executing unwanted logic. This condition manifests only when the spend amount is zero, which is a legitimate edge case for many legitimate operations, making the bug easy to overlook during code review. The issue was discovered during a security audit that included unit tests exercising zero‑value spend calls; the test demonstrated that the fallback of a mock recipient contract was invoked with the wallet address as the caller, confirming the bypass. Detecting the problem in production can be difficult because zero‑value transfers are often considered harmless and may not emit events or change balances, so developers may not notice the unauthorized external call. The proper fix is to move the isApproved() check before the early‑return, ensuring that permission validation occurs regardless of the transfer amount. This aligns the function with the broader class of “authorization bypass on zero‑value paths” bugs, where a guard is unintentionally skipped for a special input value, violating the intended security invariant that only approved spend permissions may trigger any external interaction from the wallet.
