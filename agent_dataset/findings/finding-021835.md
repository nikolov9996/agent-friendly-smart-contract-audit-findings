---
id: 21835
severity: "High"
---

# The `LockMint` and `BurnUnlock` modes cannot be used

## Description

`LockMint` and `BurnUnlock` modes refer to the following:

  * `LockMint`: Tokens are locked on the source chain and minted on the target chain.
  * `BurnUnlock`: Tokens are burned on the source chain and unlocked on the target chain.

However, because the `ChakraSettlementHandler` protocol is responsible for both processing remote `cross-chain messages` and sending `cross-chain messages` to remote chains, a single mode setting cannot handle both tasks simultaneously. This results in one of the tasks’ functionalities being unavailable due to incorrect protocol implementation.

## Proof of Concept

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
    ...
    if (payload_type == PayloadType.ERC20) {
        {
            ERC20TransferPayload memory transfer_payload = codec
                .deocde_transfer(msg_payload);
            if (mode == SettlementMode.MintBurn) {
                ...
            } else if (mode == SettlementMode.LockUnlock) {
                ...
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
    ...
}
```
In the Cairo program, the same issue also exists.
```cairo
#[abi(embed_v0)]
impl ERC20HandlerImpl of IERC20Handler<ContractState> {
    fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{
        assert(to_handler == get_contract_address(),'error to_handler');

        assert(self.settlement_address.read() == get_caller_address(), 'not settlement');

        assert(self.support_handler.read((from_chain, from_handler)) && 
                self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 'not support handler');

        let message :Message= decode_message(payload);
        let payload_type = message.payload_type;
        assert(payload_type == PayloadType::ERC20, 'payload type not erc20');
        let payload_transfer = message.payload;
        let transfer = decode_transfer(payload_transfer);
        assert(transfer.method_id == ERC20Method::TRANSFER, 'ERC20Method must TRANSFER');
        let erc20 = IERC20MintDispatcher{contract_address: self.token_address.read()};
        let token = IERC20Dispatcher{contract_address: self.token_address.read()};
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

## Recommendation

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
                _erc20_unlock(
                    AddressCast.to_address(transfer_payload.to),
                    transfer_payload.amount
                );
                return true;
            } else if (mode == SettlementMode.BurnUnlock) {
                _erc20_mint(
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
In Cairo:
```cairo
impl ERC20HandlerImpl of IERC20Handler<ContractState> {
    fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{
        assert(to_handler == get_contract_address(),'error to_handler');

        assert(self.settlement_address.read() == get_caller_address(), 'not settlement');

        assert(self.support_handler.read((from_chain, from_handler)) && 
                self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 'not support handler');

        let message :Message= decode_message(payload);
        let payload_type = message.payload_type;
        assert(payload_type == PayloadType::ERC20, 'payload type not erc20');
        let payload_transfer = message.payload;
        let transfer = decode_transfer(payload_transfer);
        assert(transfer.method_id == ERC20Method::TRANSFER, 'ERC20Method must TRANSFER');
        let erc20 = IERC20MintDispatcher{contract_address: self.token_address.read()};
        let token = IERC20Dispatcher{contract_address: self.token_address.read()};
        if self.mode.read() == SettlementMode::MintBurn{
            erc20.mint_to(u256_to_contract_address(transfer.to), transfer.amount);
        }else if self.mode.read() == SettlementMode::LockMint{
            token.transfer(u256_to_contract_address(transfer.to), transfer.amount);

        }else if self.mode.read() == SettlementMode::BurnUnlock{
            erc20.mint_to(u256_to_contract_address(transfer.to), transfer.amount);
        }else if self.mode.read() == SettlementMode::LockUnlock{
            token.transfer(u256_to_contract_address(transfer.to), transfer.amount);
        }
        
        return true;
    }
```
The Warden and its duplicates outline a **design-related flaw** that is shared across the Solidity and Cairo implementations in relation to how the `LockMint` and `BurnUnlock` systems are defined, disallowing certain configurations from ever functioning properly. These configurations are expected to be a normal likelihood event due to the system’s intents to be deployed across multiple chains, rendering this submission and its duplicates to be proper high-risk criticism of the system’s design.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a design‑level logic error in the cross‑chain settlement handler of the Chakra protocol. The handler is responsible for both receiving remote messages and sending messages to other chains, but the enumeration of settlement modes (MintBurn, LockUnlock, LockMint, BurnUnlock) is implemented incorrectly for the LockMint and BurnUnlock options. When the contract is configured in LockMint mode, the code calls the unlock function instead of minting the corresponding tokens on the destination chain; conversely, when configured in BurnUnlock mode, the code calls the mint function instead of unlocking previously burned tokens. Because the same handler cannot simultaneously act as a source‑chain lock and a destination‑chain mint, the single mode setting makes one of the two required actions impossible. As a result, cross‑chain ERC20 transfers that rely on LockMint or BurnUnlock never complete: tokens may be locked on the source chain and never minted, or may be burned and never unlocked, leaving user balances unchanged or disappearing. The issue manifests whenever a cross‑chain transfer is processed with payload_type ERC20 and the settlement mode is set to LockMint or BurnUnlock. Affected parties include any user attempting to move assets across chains using those modes, as well as the protocol itself because accounting assumptions (total supply consistency across chains) are violated. The flaw was discovered during a manual audit that compared the intended business logic of lock‑mint and burn‑unlock flows with the actual function calls in both Solidity and Cairo implementations. The problem is subtle because the contract compiles, the message passes basic validation, and no revert occurs; only the final token balances reveal the mismatch. To remediate, the settlement handler must be refactored so that each mode triggers the correct lifecycle operation: LockMint should lock tokens on the source chain and mint on the target, BurnUnlock should burn on the source and unlock on the target, or the protocol should split the responsibilities into separate inbound and outbound handlers. Additionally, the mode enumeration should be validated to prevent contradictory configurations.
