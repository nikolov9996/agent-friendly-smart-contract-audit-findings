---
id: 25367
severity: "Low/Info"
---

# Immutable variables are emitted in events

## Description

The following immutable variables are unnecessarily included in event emissions:

- SyrupUserActions::_swap() - `syrupUsdc` in `Swap` event.
- MplUserActions::_redeemAndMigrateAndStake() - `xmpl` in `RedeemedAndMigratedAndStaked` event.

## Proof of Concept

No PoC provided.

## Recommendation

Immutable variables can not be changed, unless upgraded, so an event may not be necessary.
