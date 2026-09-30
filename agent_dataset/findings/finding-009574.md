---
id: 9574
severity: "High"
---

# CelerIMFacet incorrectly sets RelayerCelerIM as receiver

## Description

When assigning a bytes memory variable to a new variable, the new variable points to the same memory location. Changing any one variable updates the other variable. Here is a PoC as a foundry test
```solidity
function testCopy() public {
    Pp memory x = Pp({
        a: 2,
        b: address(2)
    });
    Pp memory y = x;
    y.b = address(1);
    assertEq(x.b, y.b);
}
```
Thus, when CelerIMFacet._startBridge() updates bridgeDataAdjusted.receiver, _bridgeData.receiver is implicitly updated too. This makes the receiver on the destination chain to be the relayer address.
```solidity
// case 'yes': bridge + dest call - send to relayer
ILiFi.BridgeData memory bridgeDataAdjusted = _bridgeData;
bridgeDataAdjusted.receiver = address(relayer);
(bytes32 transferId, address bridgeAddress) = relayer
    .sendTokenTransfer{ value: msgValue }(bridgeDataAdjusted, _celerIMData);
// call message bus via relayer incl messageBusFee
relayer.forwardSendMessageWithTransfer{value: _celerIMData.messageBusFee}(
    _bridgeData.receiver,
    uint64(_bridgeData.destinationChainId),
    bridgeAddress,
    transferId,
    _celerIMData.callData
);
```

## Proof of Concept

no poc

## Recommendation

Remove bridgeDataAdjusted and work with _bridgeData as follows:
```solidity
// case 'yes': bridge + dest call - send to relayer
address receiver = _bridgeData.receiver;
_bridgeData.receiver = address(relayer);
(bytes32 transferId, address bridgeAddress) = relayer
    .sendTokenTransfer{ value: msgValue }(_bridgeData, _celerIMData);
// call message bus via relayer incl messageBusFee
relayer.forwardSendMessageWithTransfer{value: _celerIMData.messageBusFee}(
    receiver,
    uint64(_bridgeData.destinationChainId),
    bridgeAddress,
    transferId,
    _celerIMData.callData
);
_bridgeData.receiver = receiver;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way Solidity handles memory copies of structs. When the function _startBridge creates a local variable bridgeDataAdjusted by assigning it the value of the incoming _bridgeData struct, both variables reference the same memory location. Consequently, modifying bridgeDataAdjusted.receiver also mutates _bridgeData.receiver because they are aliases rather than independent copies. In the current implementation the code sets bridgeDataAdjusted.receiver to the relayer address before calling the relayer’s sendTokenTransfer function. Because of the aliasing, the original _bridgeData.receiver is overwritten with the relayer address as well. The subsequent call to relayer.forwardSendMessageWithTransfer uses _bridgeData.receiver as the destination address on the target chain, which now incorrectly points to the relayer instead of the intended user. This misdirection causes the bridged tokens to be credited to the relayer’s account on the destination chain, effectively diverting funds away from the legitimate recipient. The impact is a loss of user funds and a breach of the protocol’s accounting guarantees, as the bridge no longer delivers assets to the address specified by the user. The bug manifests whenever the bridge is executed in the code path that adjusts the receiver field – in the provided example this is the “yes” case that performs both a token transfer and a message‑bus call. It is discovered through static analysis and a simple unit test that demonstrates that assigning one memory struct to another does not create a deep copy; changing a field in the copy reflects in the original. The issue can be hard to notice because the UI may still display the correct receiver address before the transaction is sent, and the transaction itself does not revert – it simply routes the funds to an unexpected address. From a user’s perspective the symptoms are that after initiating a bridge the user’s balance on the source chain is reduced, the destination chain shows a receipt for the relayer address, and the intended recipient receives nothing, leading to confusion and potential loss of trust. Conceptually, the bug belongs to the class of “shallow memory copy” or “reference aliasing” errors that break the intended isolation of data structures. The correct fix is to avoid creating a separate bridgeDataAdjusted variable that shares memory with the original. Instead, the code should temporarily store the original receiver address, overwrite the receiver field in the original _bridgeData only for the call to the relayer, and then restore the original value after the message‑bus call. This ensures that the destination‑chain call receives the proper receiver address while the relayer still acts as the intermediary for the token transfer, preserving the intended accounting logic and preventing unintended fund diversion.
