---
id: 9439
severity: "High"
---

# _lzReceive reverts when there is a fee refund

## Description

When sending a message to the remote ZROToken for transferring the balance of ZROToken to users, if the fee exceeds the required amount, the surplus is refunded to address(this) (the ClaimLocal contract). However, the ClaimLocal contract does not have a fallback or receive function, preventing it from receiving ETH. This causes the _lzReceive function to always revert, preventing users from claiming tokens on remote chains.
```solidity
function _lzReceive(
    Origin calldata _origin,
    bytes32 /*_guid*/,
    bytes calldata _payload,
    address /*_executor*/,
    bytes calldata /*_extraData*/
) internal override {
    (address user, uint256 zroAmount, address to) = abi.decode(_payload, (address, uint256, address));
    // solhint-disable-next-line check-send-result
    IOFT(zroToken).send{ value: msg.value }(sendParams, MessagingFee(msg.value, 0), address(this)); // @audit refund fee cannot be received by ClaimLocal
    emit ClaimRemote(user, availableToClaim, _origin.srcEid, to);
}
```
The LayerZero Endpoint contract uses SendLibrary, which uses TransferLibrary for low-level calls to return the fees.
```solidity
library Transfer {
    function native(address _to, uint256 _value) internal {
        if (_to == ADDRESS_ZERO) revert Transfer_ToAddressIsZero();
        (bool success, ) = _to.call{ value: _value }("");
        if (!success) revert Transfer_NativeFailed(_to, _value);
    }
}
```

## Proof of Concept

No poc.

## Recommendation

Add a receive function to the ClaimLocal contract to enable it to accept ETH refunds.
```solidity
+ receive() external payable {}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing payable fallback (receive) function in the ClaimLocal contract that prevents it from accepting native ETH refunds. When a user initiates a cross‑chain claim, the LayerZero endpoint calculates a messaging fee and, if the supplied fee exceeds the exact amount required, the surplus is automatically sent back to the caller address – in this case the ClaimLocal contract. Because ClaimLocal does not implement a receive() external payable or a fallback() external payable function, the low‑level call performed by Transfer.native reverts with Transfer_NativeFailed. Consequently the internal _lzReceive handler reverts every time a fee refund is attempted, aborting the entire claim flow. The impact is that users cannot successfully claim their ZRO tokens on remote chains; the transaction fails, no tokens are transferred, and the user sees no change in balance despite having paid a fee. The issue manifests only when the supplied msg.value is larger than the exact fee, which is a common situation when callers over‑estimate fees to guarantee delivery. It affects any user attempting to claim tokens across chains and also harms the protocol’s reliability because the claim mechanism is effectively broken. The bug was discovered during a security audit that inspected the interaction between the ClaimLocal contract and LayerZero’s SendLibrary, noticing that the refund path had no payable entry point. It is hard to notice because the revert occurs deep inside a library call and surfaces as a generic transfer failure rather than an obvious missing function. The class of bug is a payable fallback omission leading to native token transfer failure, a subtype of improper handling of external ETH refunds. From a user’s perspective the UI may show a “claim” button that appears to submit, but after confirmation the token balance remains unchanged and no refund is received, contradicting the expectation that the claim succeeds and any excess fee is returned. To remediate, the contract should implement a receive() external payable (or a fallback payable) function so that the refund can be accepted, allowing the _lzReceive logic to complete and the token claim event to be emitted as intended.
