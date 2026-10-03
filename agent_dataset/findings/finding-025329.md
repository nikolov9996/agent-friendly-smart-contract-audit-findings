---
id: 25329
severity: "Low/Info"
---

# MapleLoanStorage storage slot optimization.

## Description

On the MapleLoanStorage contract, a storage slot can be reduced by packing the last variable: platformServiceFeeRate (a uint64) with one of the addresses.

## Proof of Concept

No PoC provided.

## Recommendation

Pack the variables into a single storage slot. Note: This may slightly harm code readability
