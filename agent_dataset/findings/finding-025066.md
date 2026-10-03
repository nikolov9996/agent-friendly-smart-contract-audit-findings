---
id: 25066
severity: "Medium"
---

# Users always pay fee on the full swapped amount in the DeliHook, even if the swap is smaller

## Description



## Proof of Concept

None

## Impact

If the user specifies a sqrtPrice limit that only swaps 50% of the input/output funds, and the fee is calculated on 100% of the amount, it would be an error of 100%, high severity, and scales with the amount swapped.

## Recommendation

Adjust the fee for the actual amount swapped.
