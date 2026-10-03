---
id: 25061
severity: "Low/Info"
---

# Incorrect RefundClaim event due to deleting idoConfig.accountPositions[msg.sender]

## Description

The refund event is emitted as `emit RefundClaim(idoRoundId, msg.sender, pos.amount, pos.fyAmount);`. `pos` is defined as `IDOStructs.Position storage pos = idoConfig.accountPositions[msg.sender];`. Before emitting the event, the mapping is deleted `delete idoConfig.accountPositions[msg.sender];`. Thus, when the event is emitted, `pos.amount` and `pos.fyAmount` have been deleted.

## Proof of Concept

No PoC provided.

## Recommendation

Emit the event before deleting the mapping.
