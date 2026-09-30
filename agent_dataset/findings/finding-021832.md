---
id: 21832
severity: "High"
---

# `ChakraSettlement.receive_cross_chain_msg` and `ChakraSettlement.receive_cross_chain_callback` functions do not ensure that receiving `ChakraSettlement` contract’s `contract_chain_name` must match `to_chain` corresponding to respective `txid` input though they should

## Description

Because the `ChakraSettlement.receive_cross_chain_msg` function does not ensure that the receiving `ChakraSettlement` contract’s `contract_chain_name` must match the `to_chain` corresponding to its `txid` input, the signatures that should only be used for calling the `ChakraSettlement.receive_cross_chain_msg` function on `to_chain` A can also be allowed to be used on `to_chain` B. As a result, the handler on `to_chain` B can incorrectly mint or transfer tokens to recipients though such recipients should only receive such token amounts on `to_chain` A and not on `to_chain` B.

Similarly, since the `ChakraSettlement.receive_cross_chain_callback` function does not ensure that the receiving `ChakraSettlement` contract’s `contract_chain_name` must match the `to_chain` associated with its `txid` input, the signatures that should only be used for calling the `ChakraSettlement.receive_cross_chain_callback` function on `to_chain` A can also be allowed to be used on `to_chain` B. As a result, `to_chain` B’s handler’s `receive_cross_chain_callback` function logics can be incorrectly triggered, such as burning the corresponding token amount held by such handler on `to_chain` B under the `MintBurn` mode though such token amount should only be burned on `to_chain` A and not on `to_chain` B.

## Proof of Concept

When a validator is deterministically deployed, it can have the same address on different chains. When a handler is deterministically deployed, it can have the same address on different chains. Therefore, it is possible that the validators have the same addresses on two different `to_chain` chains while the number of required validators are the same on both chains, and the handler has the same address on these two `to_chain` chains as well. Moreover, such handler can whitelist the same `from_chain`-`from_handler` combination on both `to_chain` chains.

Suppose such situation occurs for `to_chain` A and B, the validators on `to_chain` A can sign for a cross-chain message in which such signatures should only be used on `to_chain` A and should not be allowed to be used on `to_chain` B. However, since the `ChakraSettlement.receive_cross_chain_msg` function does not ensure that the receiving `ChakraSettlement` contract’s `contract_chain_name` must match the `to_chain` corresponding to its `txid` input, the `ChakraSettlement.receive_cross_chain_msg` function on `to_chain` B can be successfully called with the `txid`, `from_chain`, `from_address`, `from_handler`, `to_handler`, and `payload`, which were encoded in the signed message hash for the signatures that should only be used on `to_chain` A.

In this case:

  * `signature_verifier.verify(message_hash, signatures, sign_type)` would return `true` because the corresponding validators, which signed the signatures for `to_chain` A, have the same addresses on both `to_chain` A and B, and both chains have the same number of required validators;
  * `ISettlementHandler(to_handler).receive_cross_chain_msg` would be called successfully because the corresponding `to_handler` that is encoded for the signatures to be used on `to_chain` A also exists on `to_chain` B with the same address;
  * `is_valid_handler(from_chain, from_handler)` would be `true` when further calling the `ChakraSettlementHandler.receive_cross_chain_msg` function because the `from_chain`-`from_handler` combination that is encoded for the signatures to be used on `to_chain` A is also whitelisted by such `to_handler` on `to_chain` B.

Thus, such `ChakraSettlement.receive_cross_chain_msg` function call on `to_chain` B would be successful, which causes such signatures that should only be used for calling the `ChakraSettlement.receive_cross_chain_msg` function on `to_chain` A to also be allowed to be used on `to_chain` B.

```solidity
function receive_cross_chain_msg(
    uint256 txid,
    string memory from_chain,
    uint256 from_address,
    uint256 from_handler,
    address to_handler,
    PayloadType payload_type,
    bytes calldata payload,
    uint8 sign_type, // validators signature type /  multisig or bls sr25519
    bytes calldata signatures // signature array
) external {
    {
        // verify signature
        bytes32 message_hash = keccak256(
            abi.encodePacked(
                txid,
                from_chain,
                from_address,
                from_handler,
                to_handler,
                keccak256(payload)
            )
        );

        require(
            signature_verifier.verify(message_hash, signatures, sign_type),
            "Invalid signature"
        );

        require(
            receive_cross_txs[txid].status == CrossChainMsgStatus.Unknow,
            "Invalid transaction status"
        );
    }

    receive_cross_txs[txid] = ReceivedCrossChainTx(
        txid,
        from_chain,
        contract_chain_name,
        from_address,
        from_handler,
        address(this),
        payload,
        CrossChainMsgStatus.Pending
    );

    bool result = ISettlementHandler(to_handler).receive_cross_chain_msg(
        txid,
        from_chain,
        from_address,
        from_handler,
        payload_type,
        payload,
        sign_type,
        signatures
    );

    CrossChainMsgStatus status = CrossChainMsgStatus.Failed;
    if (result == true) {
        status = CrossChainMsgStatus.Success;
        receive_cross_txs[txid].status = CrossChainMsgStatus.Success;
    } else {
        receive_cross_txs[txid].status = CrossChainMsgStatus.Failed;
    }

    emit CrossChainHandleResult(
        txid,
        status,
        contract_chain_name,
        from_chain,
        address(to_handler),
        from_handler,
        payload_type
    );
}

function receive_cross_chain_msg(
    uint256 /**txid */,
    string memory from_chain,
    uint256 /**from_address */,
    uint256 from_handler,
    PayloadType payload_type,
    bytes calldata payload,
    uint8 /**sign type */,
    bytes calldata /**signaturs */
) external onlySettlement returns (bool) {
    //  from_handler need in whitelist
    if (is_valid_handler(from_chain, from_handler) == false) {
        return false;
    }
    bytes calldata msg_payload = MessageV1Codec.payload(payload);

    require(isValidPayloadType(payload_type), "Invalid payload type");

    if (payload_type == PayloadType.ERC20) {
        // Cross chain transfer
        {
            // Decode transfer payload
            ERC20TransferPayload memory transfer_payload = codec
                .deocde_transfer(msg_payload);

            if (mode == SettlementMode.MintBurn) {
                _erc20_mint(
                    AddressCast.to_address(transfer_payload.to),
                    transfer_payload.amount
                );
                return true;
            } else if (mode == SettlementMode.LockUnlock) {
                _erc20_unlock(
                    AddressCast.to_address(transfer_payload.to),
                    transfer_payload.amount
                );

                return true;
            } else if (mode == SettlementMode.LockMint) {
                _erc20_mint(
                    AddressCast.to_address(transfer_payload.to),
                    transfer_payload.amount
                );
                return true;
            } else if (mode == SettlementMode.BurnUnlock) {
                _erc20_unlock(
                    AddressCast.to_address(transfer_payload.to),
                    transfer_payload.amount
                );
                return true;
            }
        }
    }

    return false;
}
```

Similarly, when the same situation occurs for `to_chain` A and B, the `ChakraSettlement.receive_cross_chain_callback` function on `to_chain` B can also be successfully called with the `txid`, `from_handler`, `to_handler`, and `status`, which were encoded in the signed message hash for the signatures that should only be used on `to_chain` A, because the `ChakraSettlement.receive_cross_chain_callback` function does not ensure that the receiving `ChakraSettlement` contract’s `contract_chain_name` must match the `to_chain` associated with its `txid` input.

For the same reasons described for the case involving the `ChakraSettlement.receive_cross_chain_msg` function, calling the `ChakraSettlement.receive_cross_chain_callback` function in this case would cause `signature_verifier.verify(message_hash, signatures, sign_type)` to return `true`, `ISettlementHandler(to_handler).receive_cross_chain_callback` to be called successfully, and `is_valid_handler(from_chain, from_handler)` to be `true` when further calling the `ChakraSettlementHandler.processCrossChainCallback` function. Hence, such `ChakraSettlement.receive_cross_chain_callback` function call on `to_chain` B would be successful, which causes such signatures that should only be used for calling the `ChakraSettlement.receive_cross_chain_callback` function on `to_chain` A to also be allowed to be used on `to_chain` B.

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

function processCrossChainCallback(
    uint256 txid,
    string memory from_chain,
    uint256 from_handler,
    address to_handler,
    CrossChainMsgStatus status,
    uint8 sign_type,
    bytes calldata signatures
) internal {
    require(
        create_cross_txs[txid].status == CrossChainMsgStatus.Pending,
        "Invalid transaction status"
    );

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
}

function receive_cross_chain_callback(
    uint256 txid,
    string memory from_chain,
    uint256 from_handler,
    CrossChainMsgStatus status,
    uint8 /* sign_type */, // validators signature type /  multisig or bls sr25519
    bytes calldata /* signatures */
) external onlySettlement returns (bool) {
    //  from_handler need in whitelist
    if (is_valid_handler(from_chain, from_handler) == false) {
        return false;
    }

    require(
        create_cross_txs[txid].status == CrossChainTxStatus.Pending,
        "invalid CrossChainTxStatus"
    );

    if (status == CrossChainMsgStatus.Success) {
        if (mode == SettlementMode.MintBurn) {
            _erc20_burn(address(this), create_cross_txs[txid].amount);
        }

        create_cross_txs[txid].status = CrossChainTxStatus.Settled;
    }

    if (status == CrossChainMsgStatus.Failed) {
        create_cross_txs[txid].status = CrossChainTxStatus.Failed;
    }

    return true;
}
```

## Recommendation

The `ChakraSettlement.receive_cross_chain_msg` and `ChakraSettlement.receive_cross_chain_callback` functions can be updated to check if the receiving `ChakraSettlement` contract’s `contract_chain_name` matches the `to_chain` associated with the respective `txid` input and revert if not matched.

The Warden outlines that replay attacks are possible when receiving funds due to the absence of the `to_chain` variable’s validation. This allows the same payload signed by the Chakra validators to be replayed across multiple chains incorrectly, indicating a high-risk vulnerability.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing validation of the destination chain identifier in the ChakraSettlement contract’s cross‑chain entry points. Both the receive_cross_chain_msg and receive_cross_chain_callback functions record the contract’s own chain name (contract_chain_name) but never compare it with the to_chain value that is implicitly encoded in the transaction identifier (txid). Because of this omission, a signed cross‑chain message that was created for a specific target chain (for example chain A) can be replayed on a different chain (for example chain B) where the validator set and handler contracts share the same addresses. The signature verification succeeds, the handler is considered whitelisted, and the settlement logic is executed on the wrong chain. On the receiving side this leads to unauthorized minting of tokens when the settlement mode is MintBurn, or to an incorrect unlock operation in other modes. Similarly, the callback logic can trigger a burn on the wrong chain, destroying tokens that should have remained on the original chain. The impact is a breach of the protocol’s accounting invariants: token supply may be inflated on one chain or deflated on another, users may see unexpected token balances, or their funds may disappear entirely. The bug manifests when the same validator set and handler contracts are deployed deterministically on multiple chains, a situation that is realistic in cross‑chain environments. It is difficult to notice because the signatures appear valid, the contract emits the expected events, and there is no explicit error – the only symptom is an unexpected change in token balances on a chain that was not intended to receive the transfer. The issue was discovered during a Code4rena audit that examined the cross‑chain message handling logic and identified the absent chain‑match check. To remediate, the contract should store the intended to_chain for each txid and enforce that contract_chain_name equals this value before processing the message or callback, reverting the transaction if the check fails. This simple additional verification eliminates the replay vector and restores the intended one‑to‑one relationship between a signed cross‑chain message and its target chain, preserving token accounting across all supported chains.
