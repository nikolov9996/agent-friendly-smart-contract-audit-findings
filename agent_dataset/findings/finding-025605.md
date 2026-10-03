---
id: 25605
severity: "Crit/High"
---

# Note footers should not be 0 in curveRemoveLiquidity() if the corresponding assetOuts are non null

## Description

In curveRemoveLiquidity(), the note footer should not be allowed to be 0 if assetOut is non null, as this could lead to duplicate note footers.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the note footer is 0 but the corresponding asset out is not.
