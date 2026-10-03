---
id: 25622
severity: "Medium"
---

# No support for fee on transfer tokens

## Description

Fee on transfer tokens are not correctly dealt, as the transferFrom() call is expected to transfer exactly the requested amount. However, this is not the case for tokens that charge a fee on transfer.

## Proof of Concept

No PoC provided.

## Recommendation

To support these tokens, check the balance before calling safeTransferFrom() and compare with the new balance, getting the actual transferred amount.
