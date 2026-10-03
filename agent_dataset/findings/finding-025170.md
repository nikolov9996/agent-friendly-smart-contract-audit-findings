---
id: 25170
severity: "Crit/High"
---

# The health of a ProtectedListing is incorrectly calculated if the tokenTaken has be changed through ProtectedListings::adjustPosition().

## Description



## Proof of Concept

No PoC needed.

## Impact

The impact of this serious vulnerability is that the user is being in more debt than what he should have been, since he accrues interest for a period that he had not actually taken that debt. In this way, while he expects his `tokenTaken` to be increased by `x` amount (as it would be fairly happen), he sees his debt to be inflated by `x compounded`. This can cause instant and unfair liquidations and **loss of funds** for users unfairly taken into more debt.

## Recommendation

To mitigate this vulnerability successfully, consider updating the checkpoints of the `ProtectedListing` whenever an adjustment is happening in the `position`, so the debt to be compounded correctly.
