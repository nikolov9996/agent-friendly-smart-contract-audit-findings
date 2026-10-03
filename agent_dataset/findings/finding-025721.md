---
id: 25721
severity: "Low/Info"
---

# User deposits are exposed to protocol risk before being able to do anything

## Description

depositCollateral() and related functions transfer funds from the user, but only after the delay or the sequencer submission is the balance of the user updated. This poses a risk for the user that may lose the funds without having the opportunity to do something about them.

A simple example would be having a single user in the protocol who deposited, accuring deposit multiplier. If this user withdrew, it would get some of the pending deposit collateral.

## Proof of Concept

No PoC provided.

## Recommendation

Endpoint::handleDepositTransfer() could move the funds to a temporary address and only when the deposit is submitted are the funds transferred to the clearing house.
