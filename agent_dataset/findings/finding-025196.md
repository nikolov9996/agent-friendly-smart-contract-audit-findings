---
id: 25196
severity: "Medium"
---

# It's impossible to do a depositETH action on xReceive(...) in ConnextRouter

## Description

The ConnextRouter allows users to bridge items from one chain to another and perform arbitrary actions there. Currently, the ConnextRouter checks, in the depositETH action, that the amount is equal to the msg.value sent.

This means that for xReceive(...) calls, which never send native, it's impossible to deposit ETH.

## Proof of Concept

No PoC provided.

## Recommendation

The check that the amount is equal to the msg.value is unnecessary, given that it should be impossible to steal an already existing ETH from the router due to the balance checks.

Additionally, this should be implemented for consistency, because for ERC20 tokens this check does not exist currently; users can specify the router as the sender in deposit actions, effectively not checking if the users sent the tokens.

Thus, remove

```solidity
if (amount != msg.value) {
    revert BaseRouter__bundleInternal_insufficientETH();
}
```
