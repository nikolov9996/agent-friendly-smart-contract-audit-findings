---
id: 25182
severity: "Low/Info"
---

# xBundle(...) and xReceive(...) should have nonReentrant modifiers

## Description

xBundle(...) and xReceive(...) make several external calls and check the balances before and after these calls. It's safer to include nonReentrant modifiers to prevent reentrancy.

## Proof of Concept

No PoC provided.

## Recommendation

Check the [Connext implementation](<https://github.com/connext/monorepo/blob/main/packages/deployments/contracts/contracts/core/connext/facets/BaseConnextFacet.sol#L51>) for an example. Using non zero state variables as mutex saves gas, because the second write is to the same slot as the first write.

Add a check such that if msg.sender is the flasher, it can reenter.
