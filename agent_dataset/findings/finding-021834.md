---
id: 21834
severity: "High"
---

# Handler’s `receive_cross_chain_callback`

## Description

When a validator invokes `Settlement.cairo`’s `receive_cross_chain_callback()`, they will pass the `cross_chain_msg_status` as an input and base on that the msg status should be set on the source chain. Means, if the `cross_chain_msg_status` is given as `SUCCESS` then the msg status on the source chain will be set as `CrossChainTxStatus::SETTLED` and if it is not `SUCCESS` then it should simply set the status to `CrossChainTxStatus::FAILED` but in the cairo implementation, the `cross_chain_msg_status` is completely ignored:

```solidity
fn receive_cross_chain_callback(ref self: ContractState, cross_chain_msg_id: felt252, from_chain: felt252, to_chain: felt252,
from_handler: u256, to_handler: ContractAddress, cross_chain_msg_status: u8) -> bool{
    assert(to_handler == get_contract_address(),'error to_handler');

    assert(self.settlement_address.read() == get_caller_address(), 'not settlement');

    assert(self.support_handler.read((from_chain, from_handler)) && 
            self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 'not support handler');

    let erc20 = IERC20MintDispatcher{contract_address: self.token_address.read()};
    if self.mode.read() == SettlementMode::MintBurn{
        erc20.burn_from(get_contract_address(), self.created_tx.read(cross_chain_msg_id).amount);
    }
    let created_tx = self.created_tx.read(cross_chain_msg_id);
    ///@audit-issue M cross_chain_msg_status not checked like in the solidity instance, this will always set tx_status as settled and return true and never Failed!
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

The `tx_status` is directly set as `SETTLED`, which means it will be always get marked as `SETTLED` even when the Msg gets failed on the destination chain.

Also, as it doesn’t check the `cross_chain_msg_status`, this will always burn the tokens (when the MODE is MintBurn), which is not the case when we look at the solidity instance

```solidity
if self.mode.read() == SettlementMode::MintBurn{
    erc20.burn_from(get_contract_address(), self.created_tx.read(cross_chain_msg_id).amount);
}
```

## Proof of Concept

In the solidity instance both the status is checked and tokens only get burned when the status gets marked as SETTLED:

```solidity
if (status == CrossChainMsgStatus.Success) {
    if (mode == SettlementMode.MintBurn) {
        _erc20_burn(address(this), create_cross_txs[txid].amount);
    }

    create_cross_txs[txid].status = CrossChainTxStatus.Settled;
}

if (status == CrossChainMsgStatus.Failed) {
    create_cross_txs[txid].status = CrossChainTxStatus.Failed;
}
```

## Recommendation

Make sure to check the given status and mark the `tx_status` base on that.

The submission details how the callback leg of a `MintBurn` mode bridge will always burn the tokens regardless of whether the transaction actually succeeded on the destination chain.

This indicates a high-risk issue within the codebase that would lead to fund loss if the destination chain’s execution fails.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the cross‑chain settlement handler’s receive_cross_chain_callback function implemented in Cairo. The function receives a cross_chain_msg_status parameter that indicates whether the message on the destination chain succeeded or failed. However, the implementation completely ignores this status and unconditionally writes the transaction record with tx_status set to CrossChainTxStatus::SETTLED. Because the code also executes a token burn when the settlement mode is MintBurn, the burn is performed regardless of the actual outcome of the cross‑chain operation. The root cause is a missing conditional check that should compare cross_chain_msg_status against the expected SUCCESS value before updating state and burning tokens. An attacker (or any validator) can invoke the callback with a failed status, but the contract will still mark the transaction as settled and burn the locked tokens, effectively destroying user funds. This flaw manifests only when the bridge operates in MintBurn mode and the destination chain reports a failure; under those conditions the source‑chain record is incorrectly marked as settled and the token balance of the contract is reduced permanently. Users experience the symptom of a transaction appearing successful in the UI while their tokens disappear, leading to a mismatch between expected receipt of funds and the reality of a zero balance. The issue was discovered during a manual audit that compared the Cairo implementation with the reference Solidity version, which correctly checks the status before burning and updating the record. It is hard to notice because the function returns true without reverting, giving the impression of a successful callback, and the incorrect status is not emitted in logs. Conceptually, this is a classic “status‑validation bypass” or “incorrect state transition” bug where external input is ignored, breaking accounting invariants. The proper fix is to add a branch that checks cross_chain_msg_status: if it equals SUCCESS, perform the burn (when in MintBurn mode) and set tx_status to SETTLED; otherwise set tx_status to FAILED and skip the burn, mirroring the Solidity logic. This restores the intended business rule that funds are only burned when the cross‑chain transfer truly succeeds, preserving user balances and protocol integrity.
