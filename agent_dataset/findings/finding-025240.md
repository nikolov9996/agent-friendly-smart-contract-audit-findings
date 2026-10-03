---
id: 25240
severity: "Low/Info"
---

# In GReservePool, remove unnecessary logic

## Description

In the function withdraw(), the variable amountTransfered is going to be equal to the biggest of two variables, either totalWithdraw or amount.

Since totalWithdraw will either be bigger than amount or the same, there is no need to check if one is bigger than the other as totalWithdraw will always be the correct value.

Therefore you can just use totalWithdraw for the transfer.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
