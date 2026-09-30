---
id: 21836
severity: "High"
---

# Malicious actors can manipulate the `cross_chain_callback` callback

## Description

Because the validator’s signature message does not include the `from_chain` field, a malicious actor can preemptively execute the validator’s transaction with an incorrect `from_chain` field. This can cause the status of `create_cross_txs[txid]` to become a `Failed` state, preventing it from being executed again.

## Proof of Concept

This is the `receive_cross_chain_callback` function
```solidity
function receive_cross_chain_callback(
    uint256 txid,
    string memory from_chain,
    uint256 from_handler,
    address to_handler,
    CrossChainMsgStatus status,
    uint8 sign_type,
    bytes calldata signatures
) external {
    verifySignature(
        txid,
        from_handler,
        to_handler,
        status,
        sign_type,
        signatures
    );
    processCrossChainCallback(
        txid,
        from_chain,
        from_handler,
        to_handler,
        status,
        sign_type,
        signatures
    );
    emitCrossChainResult(txid);
}
```
In the signature verification process, we found that the signature message does not include the `from_chain` field.
```solidity
function verifySignature(
    uint256 txid,
    uint256 from_handler,
    address to_handler,
    CrossChainMsgStatus status,
    uint8 sign_type,
    bytes calldata signatures
) internal view {
    bytes32 message_hash = keccak256(
        abi.encodePacked(txid, from_handler, to_handler, status)
    );

    require(
        signature_verifier.verify(message_hash, signatures, sign_type),
        "Invalid signature"
    );
}
```
In this scenario, a malicious actor could execute the following attack steps:

  1. Front-run the caller’s transaction, providing correct signatures and other parameters, but with an incorrect `from_chain` field, causing the verifySignature validation to pass.
  2. In the `processCrossChainCallback` function, call `handler::receive_cross_chain_callback`.
  3. Due to the incorrect `from_chain`, the `is_valid_handler` function returns false, which causes `handler::receive_cross_chain_callback` to return false.

```solidity
if (is_valid_handler(from_chain, from_handler) == false) {
    return false;
}
```

  4. If `handler::receive_cross_chain_callback returns` false, it will cause `create_cross_txs[txid].status` to be set to `Failed`.

```solidity
if (
    ISettlementHandler(to_handler).receive_cross_chain_callback(
        txid,
        from_chain,
        from_handler,
        status,
        sign_type,
        signatures
    )
) {
    create_cross_txs[txid].status = status;
} else {
    create_cross_txs[txid].status = CrossChainMsgStatus.Failed;
}
```

## Recommendation

```solidity
function receive_cross_chain_callback(
    uint256 txid,
    string memory from_chain,
    uint256 from_handler,
    address to_handler,
    CrossChainMsgStatus status,
    uint8 sign_type,
    bytes calldata signatures
) external {
    verifySignature(
        txid,
        from_chain,
        from_handler,
        to_handler,
        status,
        sign_type,
        signatures
    );
    ...
}
```
```solidity
function verifySignature(
    uint256 txid,
    string memory from_chain,
    uint256 from_handler,
    address to_handler,
    CrossChainMsgStatus status,
    uint8 sign_type,
    bytes calldata signatures
) internal view {
    bytes32 message_hash = keccak256(
        abi.encodePacked(txid, from_chain, to_handler, status)
    );

    require(
        signature_verifier.verify(message_hash, signatures, sign_type),
        "Invalid signature"
    );
}
```
The Warden has identified a mechanism via which the third leg of a transaction can be blocked via a front-running attack, causing the transaction to indicate a failure status even though it would have normally been executed otherwise.

I consider this to be a valid high-severity issue as the status of all transactions can be trivially sabotaged to a failure state during their final callback leg.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing binding of the originating chain identifier (from_chain) in the validator’s signed message that is used to authenticate the final cross‑chain callback. Because the signature only covers the transaction id, the source handler address and the status, an attacker can front‑run the legitimate call, supply a valid signature that matches the signed fields, and deliberately set an incorrect from_chain value. The signature verification therefore succeeds, but later the callback logic checks whether the supplied from_chain matches a registered handler via is_valid_handler. Since the from_chain is wrong, the handler rejects the callback and the bridge contract records the transaction status as Failed. This can be triggered whenever a cross‑chain transaction reaches its third leg and the contract relies on the unchecked from_chain field. Users attempting to move assets across chains see their transfers marked as failed even though they provided correct signatures, leading to missing or stuck funds and a loss of confidence in the protocol. The issue was discovered during a security audit that examined the signature verification flow and noticed that from_chain was omitted from the signed payload. It is subtle because the signature itself appears valid, so the failure only manifests later in the business logic, making it easy to overlook during testing. The proper fix is to include the from_chain value in the message that is hashed and signed, or to move the handler validation into the signed data, ensuring that any alteration of the originating chain would invalidate the signature and prevent the front‑run attack. In broader terms this is an instance of an authentication bypass caused by incomplete message signing, which breaks the accounting assumption that a cross‑chain message’s provenance cannot be forged, allowing malicious actors to sabotage transaction finalisation and potentially cause funds to become unrecoverable.
