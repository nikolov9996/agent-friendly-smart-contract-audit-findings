---
id: 25341
severity: "Low/Info"
---

# In PoolManager, requestFunds(...) repeated variable fetching from storage.

## Description

On line 221 the factory_ address is assigned from IMapleProxied(msg.sender).factory(). However, on line 225, IMapleProxied(msg.sender).factory() is called again instead of using the already fetched factory_.

## Proof of Concept

No PoC provided.

## Recommendation

Use the already fetched factory_ variable.
