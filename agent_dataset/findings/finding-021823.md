---
id: 21823
severity: "High"
---

# Invalid token address used in `ChakraSettlementHandler::cross_chain_erc20_settlement`

## Description

The `ChakraSettlementHandler` incorrectly passes the contract address instead of the token one, when creating the `create_cross_txs` transaction and when emitting the `CrossChainLocked` event. The contract depends heavily on correct event emission as the protocol’s validators listen for these events and execute state-changing operations based on them.

## Proof of Concept

The `ChakraSettlementHandler::cross_chain_erc20_settlement(...)` function processes incoming cross-chain settlement user requests and sends data to the settlement contract. The method creates `CreatedCrossChainTx` along the way:
```solidity
        struct CreatedCrossChainTx {
            uint256 txid;
            string from_chain;
            string to_chain;
            address from;
            uint256 to;
            address from_token;
            uint256 to_token;
            uint256 amount;
            CrossChainTxStatus status;
        }
```

However, in the current implementation, instead of sending the `from_token` address it sends the actual contract address:
```solidity
    create_cross_txs[txid] = CreatedCrossChainTx(
                    txid,
                    chain,
                    to_chain,
                    msg.sender,
                    to,
                    address(this), // @audit - this should be the global variable `token`
                    to_token,
                    amount,
                    CrossChainTxStatus.Pending
                );
```

When the transaction is sent to the settlement contract a `CrossChainLocked` is emitted:
```solidity
    event CrossChainLocked(
            uint256 indexed txid,
            address indexed from,
            uint256 indexed to,
            string from_chain,
            string to_chain,
            address from_token,
            uint256 to_token,
            uint256 amount,
            SettlementMode mode
        );
```

However, the method, once more sends the incorrect `from_token` address:
```solidity
    emit CrossChainLocked(
                txid,
                msg.sender,
                to,
                chain,
                to_chain,
                address(this), // @audit - this should be the global variable `token`
                to_token,
                amount,
                mode
            );
```

If we peek into the Cairo implementation we can see that the `from_token` address should indeed be the token address not the handler contract address:
```cairo
    fn cross_chain_erc20_settlement(ref self: ContractState, to_chain: felt252, to_handler: u256, to_token: u256, to: u256, amount: u256) -> felt252{
    __SNIP__
                let tx: CreatedCrossChainTx = CreatedCrossChainTx{
                        tx_id: tx_id,
                        from_chain: from_chain,
                        to_chain: to_chain,
                        from: get_contract_address(),
                        to: to,
                        from_token: self.token_address.read(), // proper token address passed
                        to_token: to_token,
                        amount: amount,
                        tx_status: CrossChainTxStatus::PENDING
                    };
    __SNIPP
    
                self.emit(
                        CrossChainLocked{
                            tx_id: tx_id,
                            from: get_caller_address(),
                            to: to,
                            from_chain: get_tx_info().unbox().chain_id,
                            to_chain: to_chain,
                            from_token: self.token_address.read(), // proper token address passed
                            to_token: to_token,
                            amount: amount
                        }
                    );
                return tx_id;
            }
```

## Recommendation

Use the correct `from_token` address in `ChakraSettlementHandler::cross_chain_erc20_settlement(...)`.
```diff
    diff --git a/solidity/handler/contracts/ChakraSettlementHandler.sol b/solidity/handler/contracts/ChakraSettlementHandler.sol
    index 5d31ef9..b9cbd6d 100644
    --- a/solidity/handler/contracts/ChakraSettlementHandler.sol
    +++ b/solidity/handler/contracts/ChakraSettlementHandler.sol
    @@ -157,7 +157,7 @@ contract ChakraSettlementHandler is BaseSettlementHandler, ISettlementHandler {
                     to_chain,
                     msg.sender,
                     to,
    -                address(this),
    +                token,
                     to_token,
                     amount,
                     CrossChainTxStatus.Pending
    @@ -215,7 +215,7 @@ contract ChakraSettlementHandler is BaseSettlementHandler, ISettlementHandler {
                 to,
                 chain,
                 to_chain,
    -            address(this),
    +            token,
                 to_token,
                 amount,
                 mode
```

The Warden has identified an invalid `event` emission and transaction data storage both of which are imperative to the proper operation of a cross-chain bridge system. 

The documentation of the project does not adequately detail how those events are consumed, and inspection of the project’s `cairo` code as well as the sponsor’s own affirmation on [issue #175](https://github.com/code-423n4/2024-08-chakra-findings/issues/175) confirms the present implementation is incorrect.

I believe a high-risk issue is acceptable for this submission due to how crucial those components are to the proper operation of a cross-chain bridge.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incorrect token address being supplied to the cross‑chain settlement logic of the Chakra bridge. In the function cross_chain_erc20_settlement the handler stores the address of the handler contract (address(this)) in the from_token field of the CreatedCrossChainTx struct and also emits the CrossChainLocked event with the same wrong address. The contract is supposed to record the ERC‑20 token contract that is being moved, but the code mistakenly uses the handler’s own address. This mistake originates from a simple copy‑and‑paste or naming error where the global variable token that holds the correct token address is ignored. Validators and off‑chain relayers watch the CrossChainLocked event to trigger the release of the corresponding token on the destination chain; because the event carries the handler address instead of the token address, the downstream system attempts to release a non‑existent or wrong token. As a result the bridge may lock the user's funds on the source chain while failing to mint or transfer the expected token on the target chain, leaving the user with a zero balance on the destination side and no way to retrieve the locked amount. The bug manifests whenever a user initiates a cross‑chain ERC‑20 settlement, i.e., each call to cross_chain_erc20_settlement. All participants – the token sender, the bridge protocol, and the validators – are affected because the accounting assumptions that the from_token field uniquely identifies the asset are violated. The issue was discovered during a manual audit that compared the Solidity handler implementation with the Cairo settlement contract, which correctly uses self.token_address.read() for from_token. The mismatch is subtle because the event still contains a valid address and the transaction does not revert, so normal testing that only checks for successful transaction receipt may miss it. The vulnerability belongs to the class of “incorrect parameter propagation” or “event emission with wrong asset identifier”, which can break cross‑chain accounting logic. To remediate, the handler must replace address(this) with the stored token variable in both the struct assignment and the event emission, ensuring that the true ERC‑20 token address is recorded and propagated to the validators.
