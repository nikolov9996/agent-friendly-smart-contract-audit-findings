---
id: 21828
severity: "High"
---

# Forcing Starknet handlers to be whitelisted on the same chain allows exploit of `BurnUnlock` mode to drain handler funds

## Description

```solidity
fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{

        assert(to_handler == get_contract_address(),"error to_handler");
        assert(self.settlement_address.read() == get_caller_address(), "not settlement");
        assert(self.support_handler.read((from_chain, from_handler)) && 
            self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), "not support handler");
    // --SNIP
}

fn receive_cross_chain_callback(ref self: ContractState, cross_chain_msg_id: felt252, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, cross_chain_msg_status: u8) -> bool{
        
        assert(to_handler == get_contract_address(),"error to_handler");
        assert(self.settlement_address.read() == get_caller_address(), "not settlement");
        assert(self.support_handler.read((from_chain, from_handler)) && 
            self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), "not support handler");
    // --SNIP

}
```
In this context, handlers on Starknet **must** whitelist themselves as supported handlers. However, this introduces a significant vulnerability: since handlers are self-whitelisted, a malicious user could send cross-chain messages to the same chain (Starknet to Starknet) and exploit the `BurnUnlock` mode as follows:

In `BurnUnlock` mode, when a cross-chain message is sent, the user’s tokens are burned, and when the message is received, the same amount of tokens is unlocked. This opens the door for malicious actors to repeatedly send cross-chain messages to themselves, resulting in a continuous unlock of tokens:

```solidity
fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{

        // --SNIP
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
}
```
By continuously sending cross-chain messages to the same chain, the malicious user can drain the handler’s funds by repeatedly unlocking tokens to their own address. As a result, other legitimate cross-chain ERC20 operations will fail due to the depletion of ERC20 tokens in the handler contract.

## Proof of Concept

no poc

## Recommendation

The self-whitelisting of handlers introduces unnecessary risk and facilitates the aforementioned vulnerability. Consider removing the check that forces handlers to be self-whitelisted:

```solidity
fn receive_cross_chain_msg(ref self: ContractState, cross_chain_msg_id: u256, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, payload: Array<u8>) -> bool{

        assert(to_handler == get_contract_address(),"error to_handler");
        assert(self.settlement_address.read() == get_caller_address(), "not settlement");
        assert(self.support_handler.read((from_chain, from_handler)) 
            && self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), "not support handler");
    // --SNIP
}

fn receive_cross_chain_callback(ref self: ContractState, cross_chain_msg_id: felt252, from_chain: felt252, to_chain: felt252,
    from_handler: u256, to_handler: ContractAddress, cross_chain_msg_status: u8) -> bool{
        
        assert(to_handler == get_contract_address(),"error to_handler");
        assert(self.settlement_address.read() == get_caller_address(), "not settlement");
        assert(self.support_handler.read((from_chain, from_handler)) 
            && self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), "not support handler");
    // --SNIP

}
```
The Warden has attempted to formulate an exploitation path of a self-cross-chain transfer; however, the assumption that a handler can be arbitrarily introduced to the system is incorrect given that the relevant function enrolling them is owner-controlled.

Hi @0xsomeone -  

> _“however, the assumption that a handler can be arbitrarily introduced to the system is incorrect given that the relevant function enrolling them is owner-controlled.”_

This is an incorrect statement because, as seen on the `receive_crosschain_msg`, the function enforces that both `to_chain` and `to_handler` as well as `from_chain` and `from_handler` are supported:

```solidity
assert(self.support_handler.read((from_chain, from_handler)) && 
       self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), "not support handler");
```
So, starknet handlers must be self-whitelisted. A malicious user can exploit this for handlers having the mode `BurnLock` and drain the handler’s funds via sending cross-chain messages from starknet to starknet to repeatedly unlock tokens to their own address, as explained in details on the report.

Hey @Abdessamed, thanks for your follow-up feedback. The term “self-whitelisted” is invalid as the contracts do not expose a mechanism for users to self-whitelist themselves. As whitelisting is an authoritative process (i.e. requires elevated privileges), we can safely assume that registered handlers are trusted implementations rather than arbitrary users.

Hi @0xsomeone - I see where the confusion is coming from. Let me reformulate:  
In this function, it checks that both `to_chain` and `to_handler` as well as `from_chain` and `from_handler` are supported:

```solidity
assert(self.support_handler.read((from_chain, from_handler)) && 
       self.support_handler.read((to_chain, contract_address_to_u256(to_handler))), 'not support handler');
```
This forces the owner to already call `set_support_handler` to add Starknet handlers as supported on the Starknet handler. Otherwise, any call to `handler_erc20::receive_cross_chain_msg` will fail.

Now, given the above, an attacker makes use of that to make the attack described on the report.

Hey @Abdessamed, thanks for clarifying! I see what the outlined vulnerability presently is, and can confirm it is a valid issue. This is indeed a good finding! I have re-instated a high-risk rating for it, and appreciate the due diligence during the PJQA process. 

To note, self-whitelisting is the act of whitelisting oneself; might be useful for future submissions!

Regarding comments about how the Chakra Network operates, in line with other rulings in the audit, we cannot make any assumptions as to what operations those nodes can and cannot filter, so we assume all operations are processed at “face-value” rendering this submission to be valid.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the design that Starknet handlers must whitelist themselves as supported handlers for both the source and destination chain in cross‑chain messages. Because the whitelist check only verifies that the (from_chain, from_handler) and (to_chain, to_handler) pairs are present in the contract's support_handler mapping, a malicious actor can craft a cross‑chain message where the source and destination are the same chain (Starknet → Starknet) and the handler address is the same whitelisted contract. In BurnUnlock settlement mode the contract burns the sender’s tokens when the message is emitted and, upon receipt, simply calls token.transfer to unlock the same amount to the recipient. When the message is sent to the same chain, the burn step does not actually remove tokens from the handler’s balance, while the transfer step repeatedly credits the attacker’s address. By looping this operation an attacker can continuously unlock tokens to themselves, draining the ERC20 balance held by the handler contract. This depletion causes legitimate cross‑chain ERC20 transfers to fail because the handler no longer holds sufficient funds. The issue was discovered during a Code4rena audit when the cross‑chain message handling logic was examined and the self‑whitelisting assertion was identified as insufficient to prevent same‑chain abuse. The bug is subtle because the same‑chain message passes all whitelist assertions and appears as a normal cross‑chain operation, making it easy to overlook during functional testing. The flaw belongs to the class of authorization‑bypass and accounting‑logic errors where a contract’s internal accounting assumes that a burn operation always precedes an unlock, an assumption that is broken when the message loops back to the same contract. From a user’s perspective the symptoms are missing or zero balances in the handler contract and unexpected receipt of tokens without any corresponding burn, effectively “funds disappear” from the protocol. The proper mitigation is to remove the self‑whitelisting requirement or to add explicit checks that reject messages where the source and destination chain are identical, or to enforce that BurnUnlock mode can only be used for genuine cross‑chain transfers, thereby preserving the intended burn‑then‑unlock accounting invariant.
