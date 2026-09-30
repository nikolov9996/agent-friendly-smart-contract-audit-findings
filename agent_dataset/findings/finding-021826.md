---
id: 21826
severity: "High"
---

# In `settlement.cairo::receive_cross_chain_msg` - the message will always be marked with `Status::SUCCESS`

## Description

```solidity
fn receive_cross_chain_msg(/*params*/) -> bool {
    //rest of the code

    let success = handler.receive_cross_chain_msg(
                    cross_chain_msg_id, 
                    from_chain, //from_chain
                    to_chain,  //to_chain
                    from_handler, //from_handler
                    to_handler , //to_handler
                    payload     //payload
                );

                let mut status = CrossChainMsgStatus::SUCCESS;

                if success{
                    status = CrossChainMsgStatus::SUCCESS;
                }else{
                    status = CrossChainMsgStatus::FAILED;
                }

    }
```
However, the way that the `handler.receive_cross_chain_msg` function is implemented, it’ll always return true, therefore marking every message as successful even if the message for some reason was a corrupted one.

And breaking one of the main invariants that states the message statuses should be tracked correctly.

## Proof of Concept

Let’s take a look at the code of the `receive_cross_chain_msg` function on the settlement.cairo contract, and specifically at the part where the call to `handler.receive_cross_chain_msg` is made:

```solidity
fn receive_cross_chain_msg(/*params*/) -> bool {
    //rest of the code

    let success = handler.receive_cross_chain_msg(
                    cross_chain_msg_id, 
                    from_chain, //from_chain
                    to_chain,  //to_chain
                    from_handler, //from_handler
                    to_handler , //to_handler
                    payload     //payload
                );

                let mut status = CrossChainMsgStatus::SUCCESS;

                if success{
                    status = CrossChainMsgStatus::SUCCESS;
                }else{
                    status = CrossChainMsgStatus::FAILED;
                }

    }
```
As you can see, the status of the messages is based on the return value of this line: `success = handler.receive_cross_chain_msg`.

Let’s see the `handler.receive_cross_chain_msg` function:

```solidity
fn receive_cross_chain_msg(
    ref self: ContractState, 
    cross_chain_msg_id: u256, 
    from_chain: felt252, 
    to_chain: felt252,
    from_handler: u256, 
    to_handler: ContractAddress, 
    payload: Array<u8>
    ) -> bool{
    
    assert(to_handler == get_contract_address(),'error to_handler');

    assert(self.settlement_address.read() == get_caller_address(), 'not settlement');

    assert(self.support_handler.read((from_chain, from_handler)) && 
            self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 
            'not support handler'); 
            //i.e (from_chain, to_handler)

    let message :Message= decode_message(payload);
    let payload_type = message.payload_type;
    
    assert(payload_type == PayloadType::ERC20, 'payload type not erc20');
    
    let payload_transfer = message.payload;
    
    let transfer = decode_transfer(payload_transfer);
    
    assert(transfer.method_id == ERC20Method::TRANSFER, 'ERC20Method must TRANSFER');
    
    let erc20 = IERC20MintDispatcher{contract_address: self.token_address.read()};
    let token = IERC20Dispatcher{contract_address: self.token_address.read()};

    // Handle the cross-chain transfer according to the settlement mode set in the contract.

    if self.mode.read() == SettlementMode::MintBurn{
        erc20.mint_to(u256_to_contract_address(transfer.to), transfer.amount);
    
    }else if self.mode.read() == SettlementMode::LockMint{
        erc20.mint_to(u256_to_contract_address(transfer.to), transfer.amount);
    
    }else if self.mode.read() == SettlementMode::BurnUnlock{
        token.transfer(u256_to_contract_address(transfer.to), transfer.amount);
    
    }else if self.mode.read() == SettlementMode::LockUnlock{
        token.transfer(u256_to_contract_address(transfer.to), transfer.amount);
    }
    
    return true;
}
```
As you can see, as long as the function doesn’t revert, it’ll always return `true`.

This shouldn’t be the case and if for some reason the message is a corrupted one, it should get marked as `FAILED` as intended by the protocol.

The functionality is correctly implemented in the solidity version:

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

        if (is_valid_handler(from_chain, from_handler) == false) {
            return false;
        }

        bytes calldata msg_payload = MessageV1Codec.payload(payload);
        require(isValidPayloadType(payload_type), "Invalid payload type");

        if (payload_type == PayloadType.ERC20) {
            {
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

## Recommendation

Implement the functionality like in the solidity handler function so it returns `false` if something goes wrong.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the settlement.cairo contract function that processes incoming cross‑chain messages. After delegating the payload handling to a separate handler contract, the settlement code records the message status based on the boolean returned by the handler. The handler implementation, however, unconditionally returns true as long as the internal asserts do not trigger a revert, meaning that even when the payload is malformed, unsupported, or fails any of the validation checks, the function still reports success. Consequently the outer function always sets the status to SUCCESS, violating the protocol invariant that message statuses must accurately reflect whether processing succeeded or failed. This flaw can be exploited by an attacker who crafts a corrupted cross‑chain message; the settlement contract will record the message as successful and may execute token minting or unlocking logic based on the assumed validity of the payload, leading to unintended token creation or loss of funds. The impact is high because it breaks accounting guarantees, allows inflation of the token supply, and can cause user balances to change in unexpected ways. The issue manifests whenever receive_cross_chain_msg is invoked, regardless of the actual content of the payload, and affects all participants relying on correct status tracking, including token holders and the overall protocol security. It was discovered during a Code4rena audit by comparing the Cairo implementation with the reference Solidity version, which correctly returns false on validation failure. The problem is subtle because the transaction does not revert and the status field appears normal, so developers may not notice that invalid messages are being accepted. To remediate, the handler should return false when any validation assert would fail, mirroring the Solidity logic, and the settlement contract should propagate that false value to set the status to FAILED, thereby restoring the intended invariant and preventing erroneous token operations.
