---
id: 25183
severity: "Low/Info"
---

# When changing addresses, use 2 step transfer and/or contract size and/or address 0x0 checks

## Description

When changing important addresses, it's best to use additional safety measures to prevent wrong addresses from being set. When the address to change is guaranteed to be a smart

```solidity
contract, a isContract check is very helpful. Another layer of protection is using 2 step
address transfer, in which a pending role is set first and only then, from the pending role
```

account, it accepts the new role.

## Proof of Concept

No PoC provided.

## Recommendation

Check every address setter and use the mentioned patterns.
