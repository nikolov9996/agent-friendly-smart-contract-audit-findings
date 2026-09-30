---
id: 21833
severity: "High"
---

# There is no refund mechanism in `ChakraSettlement.processCrossChainCallback` or `ChakraSettlementHandler.receive_cross_chain_callback` function

## Description

Because there is no refund mechanism in the `ChakraSettlement.processCrossChainCallback` or `ChakraSettlementHandler.receive_cross_chain_callback` function, when the cross-chain ERC20 settlement fails, such as due to that the source chain’s handler can be removed from the whitelist for the destination chain after the corresponding cross-chain message is initiated on the source chain and before such message is received on the destination chain, the `ChakraSettlementHandler.cross_chain_erc20_settlement` function caller cannot get back and loses the tokens that have been transferred to the source chain’s handler or burned on the source chain by such caller.

## Proof of Concept

When the `ChakraSettlementHandler.cross_chain_erc20_settlement` function is called to initiate a cross-chain ERC20 settlement, the function caller can check to ensure that the handler on the source chain is whitelisted on the destination chain. After such function call, the function caller has transferred tokens to the handler on the source chain under the `MintBurn`, `LockUnlock`, or `LockMint` mode or burned tokens on the source chain under the `BurnUnlock` mode.

```solidity
function cross_chain_erc20_settlement(
    string memory to_chain,
    uint256 to_handler,
    uint256 to_token,
    uint256 to,
    uint256 amount
) external {
    require(amount > 0, "Amount must be greater than 0");
    require(to != 0, "Invalid to address");
    require(to_handler != 0, "Invalid to handler address");
    require(to_token != 0, "Invalid to token address");

    if (mode == SettlementMode.MintBurn) {
        _erc20_lock(msg.sender, address(this), amount);
    } else if (mode == SettlementMode.LockUnlock) {
        _erc20_lock(msg.sender, address(this), amount);
    } else if (mode == SettlementMode.LockMint) {
        _erc20_lock(msg.sender, address(this), amount);
    } else if (mode == SettlementMode.BurnUnlock) {
        _erc20_burn(msg.sender, amount);
    }

    ...
}
```

Yet, after the corresponding cross-chain message is initiated on the source chain and before such message is received on the destination chain, it is possible that the `ChakraSettlementHandler.remove_handler` function is called on the destination chain, which removes the source chain’s handler from the whitelist for the destination chain. This is beyond the control of the `ChakraSettlementHandler.cross_chain_erc20_settlement` function caller because such function caller cannot know this in advance.

```solidity
function remove_handler(
    string memory chain_name,
    uint256 handler
) external onlyOwner {
    handler_whitelist[chain_name][handler] = false;
}
```

When the corresponding cross-chain message is received on the destination chain, since the handler on the source chain has been changed to be not whitelisted on the destination chain, the `ChakraSettlementHandler.receive_cross_chain_msg` function would return `false`, which marks the `status` and `receive_cross_txs[txid].status` corresponding to the cross-chain message as failed in the `ChakraSettlement.receive_cross_chain_msg` function.

```solidity
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
    ...
}

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
    ...

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
```

Back on the source chain, the `ChakraSettlement.processCrossChainCallback` and `ChakraSettlementHandler.receive_cross_chain_callback` functions are then called with the failed cross-chain message’s `status`. This notifies that the corresponding cross-chain ERC20 settlement has failed by marking the corresponding `create_cross_txs[txid].status` as failed in both the `ChakraSettlement` and `ChakraSettlementHandler` contracts. However, such `ChakraSettlement.processCrossChainCallback` and `ChakraSettlementHandler.receive_cross_chain_callback` function calls do not refund the caller of the `ChakraSettlementHandler.cross_chain_erc20_settlement` function the tokens that were transferred to the source chain’s handler or burned on the source chain by such caller.

```solidity
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

The `ChakraSettlementHandler.receive_cross_chain_callback` function can be updated to transfer the failed cross-chain ERC20 settlement’s token amount to the corresponding caller of the `ChakraSettlementHandler.cross_chain_erc20_settlement` function under the `MintBurn`, `LockUnlock`, or `LockMint` mode. If possible, such function can also be updated to mint the failed cross-chain ERC20 settlement’s token amount to the corresponding caller of the `ChakraSettlementHandler.cross_chain_erc20_settlement` function under the `BurnUnlock` mode; otherwise, if the corresponding token cannot be minted by the protocol, the protocol needs to clearly communicate with its users about the inability of refunding the failed cross-chain ERC20 settlement’s token amount under the `BurnUnlock` mode.

The submission and all its duplicates concern various ways in which the cross-chain system of the Chakra protocol can fail transactions and does not expose a mechanism to issue refunds for those failed transactions.

This issue class is significantly large, and the lack of documentation as well as insight into the Chakra node system renders it impossible to judge fairly. I believe that a refund mechanism should be set in place, and thus consider all issues related to its missing functionality to be of high severity.

To note, I believe this is a flaw arising **from the design of the system itself** and thus have grouped these issues based on the design principle they are based on. The Sponsor has expressed that the callback function is not invoked in all cases and is solely invoked in the `MintBurn` mode, indicating that a solution based on the callback mode is not in line with the desires of the Sponsor and cannot be considered the “unopinionated way” to resolve this issue. 

The lack of documentation renders granular judgments of issues outlining the absence of a refund mechanism impractical to perform as any such distinction would rely on assumptions about the system that cannot be validated.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing refund mechanism in the cross‑chain settlement flow of the Chakra protocol. When a user calls the cross_chain_erc20_settlement function, tokens are either locked in the contract or burned on the source chain depending on the settlement mode (MintBurn, LockUnlock, LockMint or BurnUnlock). After the message is sent, the destination chain validates the source handler against a whitelist. If the handler is removed from the whitelist between the time the message is sent and the time it is processed, the receive_cross_chain_msg call returns false and the cross‑chain transaction is marked as failed. The protocol then invokes processCrossChainCallback and receive_cross_chain_callback, which update the internal status to Failed but never transfer the locked tokens back to the original caller nor re‑mint burned tokens. Consequently the caller loses the amount that was originally transferred or burned, effectively causing funds to disappear. This situation occurs only when the whitelist is altered after the settlement request, a condition that is outside the caller’s control and therefore hard to anticipate. Users experience a symptom where their balance is reduced after initiating a cross‑chain transfer, yet no tokens appear on the destination chain and no refund is received; the UI may simply show a failed transaction status. The issue was discovered during a security audit that examined the settlement callbacks and identified that the failure path does not contain any logic to restore assets. The problem is subtle because the contract does not revert or emit an explicit error – it merely records a Failed status, making the loss appear as a normal outcome rather than an exploit. The bug belongs to the class of “missing compensation for failed cross‑chain operations” and violates the fundamental accounting assumption that every locked or burned amount must either be settled on the target chain or returned to the sender. To remediate, the receive_cross_chain_callback function should be extended to detect a Failed status and, depending on the settlement mode, either transfer the locked tokens back to the original caller or mint the equivalent amount for the caller in BurnUnlock mode. If minting is not possible, the protocol must clearly communicate the inability to refund and consider alternative designs such as escrow or pre‑approval checks before initiating the cross‑chain transfer.
