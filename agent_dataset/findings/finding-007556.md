---
id: 7556
severity: "High"
---

# Missing transferable Check in send

## Description

The Token.sol contract is designed to prevent token transfers unless transfersEnabled is true or msg.sender is the controller. This restriction is enforced through the transferable modifier:
```solidity
modifier transferable() {
    require(msg.sender == controller || transfersEnabled, "NON_TRANSFERABLE");
}
```
However, the send function does not apply this modifier, allowing token transfers even when transfersEnabled is false:
```solidity
_transfer(msg.sender, to, value); // @audit-issue: No transferable check, bypassing transfer restriction
emit Sent(msg.sender, msg.sender, to, value, data, "");
if (isContract(to))
    IERC777Recipient(to).tokensReceived(msg.sender, msg.sender, to, value, data, "");
```
This oversight allows anyone to transfer tokens even when transfers are explicitly disabled, breaking the intended invariant of the contract.

## Proof of Concept

no poc

## Recommendation

Add the transferable modifier to the send function to ensure transfer restrictions are enforced:
```solidity
_transfer(msg.sender, to, value);
emit Sent(msg.sender, msg.sender, to, value, data, "");
if (isContract(to))
    IERC777Recipient(to).tokensReceived(msg.sender, msg.sender, to, value, data, "");
```
This change ensures that only the controller or users sending tokens when transfersEnabled is true can execute transfers, maintaining the intended access control.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an absent transferability guard in the token contract's public send function. The contract is intended to restrict token movement unless a global flag transfersEnabled is true or the caller is the designated controller, a rule that is enforced elsewhere through a transferable modifier that checks require(msg.sender == controller || transfersEnabled, "NON_TRANSFERABLE"). However, the send function directly invokes the internal _transfer routine without applying this modifier, meaning the require check is completely bypassed. As a result, any address can call send and move tokens even when the contract owner has deliberately disabled transfers, violating the contract's core invariant that token transfers are only permitted under controlled conditions. An attacker can exploit this by simply calling send with arbitrary recipient and amount while transfersEnabled is false, causing tokens to be transferred away from holders who believe their assets are frozen. The impact includes loss of expected transfer restrictions, potential unauthorized draining of user balances, and erosion of trust in the protocol's governance model. This condition occurs whenever the contract is in a state where transfers are disabled but the send function is still accessible, which is true for all callers because there is no access control on that entry point. All token holders, the protocol’s governance, and any third‑party integrations that rely on the transfer lock are affected. The issue was discovered during a manual security audit that compared the implementation of the transferable modifier against all external‑facing functions and noticed the omission in send. It can be hard to spot because the function appears to perform a normal token transfer and emits the expected events, giving the impression that normal checks are in place, while the critical require statement is simply missing. To remediate, the send function should be protected by the same transferable modifier (or an equivalent explicit require) so that only the controller or callers when transfersEnabled is true can execute the transfer, thereby restoring the intended access control and preserving the contract’s accounting guarantees.
