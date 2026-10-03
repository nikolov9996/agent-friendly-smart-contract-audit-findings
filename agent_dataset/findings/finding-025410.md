---
id: 25410
severity: "Low/Info"
---

# The domain with 0 index in Cap::_checkRemoteStateAndAdvance() is not checked for equality

## Description

Cap::_checkRemoteStateAndAdvance() returns if not all domains have the same epoch, but the domain with index 0 is skipped in the [loop](<https://github.com/0x73696d616f/evm-eol-3s-audit/blob/eol/src/hooks/Cap.sol#L397>).

This is never a problem because the only way for it not to return is if the domains are something such as 2, 1, 1. However, as it only advances the epoch if the minimum epoch is bigger than the local domain's epoch, as the current is 1 and the minimum is 1, it will do nothing.

## Proof of Concept

No PoC provided.

## Recommendation

Consider starting the loop in index 0.
