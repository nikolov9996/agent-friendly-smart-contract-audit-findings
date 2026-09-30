---
id: 21827
severity: "High"
---

# `settlement.cairo` doesn't process callback correctly leading to `CrossChainMsgStatus` marked as SUCCESS even if it failed on destination chain

## Description

```solidity
fn receive_cross_chain_callback(
            ref self: ContractState,
            cross_chain_msg_id: felt252,
            from_chain: felt252,
            to_chain: felt252,
            from_handler: u256,
            to_handler: ContractAddress,
            cross_chain_msg_status: u8, <--
            sign_type: u8,
            signatures: Array<(felt252, felt256, bool)>,
        ) -> bool {
    //other functionality

    let success = handler.receive_cross_chain_callback(cross_chain_msg_id, from_chain, to_chain, from_handler, to_handler , cross_chain_msg_status);

                let mut state = CrossChainMsgStatus::PENDING;
                if success{
                    state = CrossChainMsgStatus::SUCCESS;
                }else{
                    state = CrossChainMsgStatus::FAILED;
                }

                self.created_tx.write(cross_chain_msg_id, CreatedTx{
                    tx_id:cross_chain_msg_id,
                    tx_status:state, <--- update the status 
                    from_chain: to_chain,
                    to_chain: from_chain,
                    from_handler: to_handler,
                    to_handler: from_handler
                });
```
The problem is that as long as the call to `handler.receive_cross_chain_callback` function was successful, the message as a whole will be marked in a `SUCCESS` state even though that `cross_chain_msg_status` could be SUCCESS or FAILED depending on if the message failed on the destination chain.

This could lead to a situation where a message fails to get processed on the destination chain, a callback is returned with `cross_chain_msg_status == FAILED` but the message is marked as `SUCCESS`.

That situation could be a user trying to bridge his tokens, the bridging fails so he doesn’t receive his tokens on the destination chain, a callback is made and the message is marked as a `SUCCESS` even though it as not successfully executed.

And if we see the code of the `handler.receive_cross_chain_callback` function, we’ll see that it’d always return true as long as it doesn’t revert:

```solidity
fn receive_cross_chain_callback(
    ref self: ContractState, 
    cross_chain_msg_id: felt256, 
    from_chain: felt256, 
    to_chain: felt256,
    from_handler: u256, 
    to_handler: ContractAddress, 
    cross_chain_msg_status: u8 
) -> bool{

    assert(to_handler == get_contract_address(),'error to_handler');
    assert(self.settlement_address.read() == get_caller_address(), 'not settlement');
    assert(self.support_handler.read((from_chain, from_handler)) && 
            self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 'not support handler');

    let erc20 = IERC20MintDispatcher{contract_address: self.token_address.read()};

    if self.mode.read() == SettlementMode::MintBurn{
        erc20.burn_from(get_contract_address(), self.created_tx.read(cross_chain_msg_id).amount);
    }

    let created_tx = self.created_tx.read(cross_chain_msg_id);
    
    self.created_tx.write(cross_chain_msg_id, CreatedCrossChainTx{
        tx_id: created_tx.tx_id,
        from_chain: created_tx.from_chain,
        to_chain: created_tx.to_chain,
        from:created_tx.from,
        to:created_tx.to,
        from_token: created_tx.from_token,
        to_token: created_tx.to_token,
        amount: created_tx.amount,
        tx_status: CrossChainTxStatus::SETTLED
    });

    return true;
}
```
The function just performs validation of the handlers, if the settlement contract calls it and returns true. These validation could all be true but the initial message could still be with a FAILED status.

This is not taken into account and could lead to a failed message being marked as a successful one.

The implementation on the solidity contract is correct:

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
        create_cross_txs[txid].status = status; <---
    
    } else {
        create_cross_txs[txid].status = CrossChainMsgStatus.Failed;
    }
}
```
As you can see, even if the call to the handler was successful, the status is updated with the `CrossChainMsgStatus` that was passed to the function and it is not automatically marked with `SUCCESS`.

This should be the case in the cairo function as well but right now the `cross_chain_msg_status` parameter is ignored.

## Proof of Concept

no poc

## Recommendation

Change this line from this:

```solidity
if success{
    state = CrossChainMsgStatus::SUCCESS;
```
to this:

```solidity
if success{
    state = cross_chain_msg_status;
```
To be consistent with the solidity implementation.

The Warden has identified that the status of a cross-chain message is not properly set when a callback is performed on the source chain.

I believe a severity of high is appropriate, as a failed cross-chain transaction would indicate it was processed successfully when this vulnerability manifests.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the cross‑chain settlement contract written in Cairo. When a message that originated on one blockchain is processed on a destination chain, the destination contract returns a status flag (SUCCESS or FAILED) through the cross_chain_msg_status argument of the receive_cross_chain_callback function. The source contract then calls a handler and records the overall message status based solely on whether the handler call returned true. Because the handler is designed to return true whenever it does not revert, the code ignores the actual cross_chain_msg_status supplied by the destination chain. Consequently, a message that failed on the destination chain – for example a token transfer that was rejected or a mint‑burn operation that did not complete – will still be marked as CrossChainMsgStatus.SUCCESS in the source contract’s bookkeeping. This logical error arises from using the boolean success of the internal call instead of propagating the status parameter, a mistake that was uncovered by comparing the Cairo implementation with the reference Solidity version where the status is correctly assigned. The bug can be exploited whenever an attacker or a faulty destination contract forces a cross‑chain operation to fail while still allowing the callback to be delivered. The source contract will then record the transaction as successful, leading the user interface to display a confirmed bridge, while the user’s tokens remain locked, burned, or never minted on the target chain. From the user’s perspective the bridge transaction appears completed, the UI shows a success badge, but the destination balance stays unchanged or becomes zero, violating the expectation that assets are transferred. The impact is a loss of funds or a mismatch in accounting that can undermine trust in the protocol. The issue manifests only when the callback is processed; normal successful transfers are unaffected. It is hard to notice because the transaction does not revert and the status flag in storage is set to SUCCESS, so no error is emitted. The proper remediation is to assign the stored state to the cross_chain_msg_status value received from the callback when the handler call succeeds, mirroring the Solidity logic, thereby ensuring that a FAILED status is recorded correctly and users receive accurate feedback about the outcome of their cross‑chain operations. This class of bug is an incorrect status handling or logical omission that leads to false‑positive success reporting in cross‑chain messaging systems.
