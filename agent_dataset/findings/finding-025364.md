---
id: 25364
severity: "Low/Info"
---

# Duplicated _permit() function

## Description

The _permit() function, utilized in the MplUserActions, SyrupRouter, and SyrupUserActions contracts, is duplicated across them.

## Proof of Concept

No PoC provided.

## Recommendation

To enhance code reusability and maintainability, this function can be relocated to the utils folder.
