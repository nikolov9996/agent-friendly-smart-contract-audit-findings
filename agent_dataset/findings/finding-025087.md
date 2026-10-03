---
id: 25087
severity: "Crit/High"
---

# BatchOut:withdrawFulfill() can be DoSed by spamming withdrawal requests, leading to OOG reverts

## Description

Anyone can schedule as many withdrawals as they want in BatchOut:scheduleWithdraw(), specifying little shares to different withdrawTo addresses. Then, in withdrawFulfill(), it will loop over all the requests in the cycle, leading to OOG reverts if enough requests were spammed.

## Proof of Concept

No PoC provided.

## Recommendation

Send as argument a number of requests to fulfill, so the OOG revert can be prevented.
