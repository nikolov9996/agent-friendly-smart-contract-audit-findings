---
id: 25132
severity: "Low/Info"
---

# Invite fees in FairLauncher::_calInviteFees() may be 0, in which case storage update could be skipped

## Description

In FairLauncher::_calInviteFees(), state updates are skipped if the directInviter is address(0), but they could also be skipped if the amount is null, which happens after the hard cap is reached.

## Proof of Concept

No PoC provided.

## Recommendation

Skip storage slot updates if the amount is null.
