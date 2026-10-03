---
id: 25018
severity: "Crit/High"
---

# cds owners can withdraw more than expected via manipulating excessProfitCumulativeValue

## Description



## Proof of Concept

N/A

## Impact

Malicious users can withdraw more profit than expected via manipulating the `excessProfitCumulativeValue` and `signauture`.

## Recommendation

Enhance the signature check. One signature can only be used for one cds owner's specific deposit index.
