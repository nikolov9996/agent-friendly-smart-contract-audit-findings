---
id: 25317
severity: "Low/Info"
---

# Consider using a time lock on critical permissioned functions.

## Description

In critical functions that may affect the decision of users to stay invested in the protocol (for example functions that set certain pool terms, fees, upgrades, etc.), there are no timelocks implemented, which will give no time for users to take their funds from the protocol and thus can deter them from interacting with Maple.

## Proof of Concept

No PoC provided.

## Recommendation

Implement timelocks in the types of functions mentioned above.
