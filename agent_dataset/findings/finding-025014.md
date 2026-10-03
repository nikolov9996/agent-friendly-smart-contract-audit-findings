---
id: 25014
severity: "Crit/High"
---

# Borrower withdrawing at a loss will cause losses for cds depositors that only withdraw after the price recovers

## Description



## Proof of Concept

POC described in the attack path section.

## Impact

Second cds depositor is not able to withdraw their cds deposit as the first cds depositor took 900 USDa even though it contributed to the downside protection, not the second one. This will also happen on a larger scale in case more borrows / depositors participate, the presented scenario was just an example.

## Recommendation

There are a few options:

1. Consider enforcing the loss on the first cds depositor as the downside protection was applied when it was in the protocol.
2. Or, increase the cds deposited amount variable when the price comes back up, even if it was down before.
