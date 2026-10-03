---
id: 25076
severity: "Low/Info"
---

# Missing fee refund on Batch.sol

## Description

The msg.value sent to Batch:deposit() might be [bigger](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L243-L245>) than the depositFeeAmount, which means that the contract will receive more native than the fee.

## Proof of Concept

No PoC provided.

## Recommendation

Place a refund mechanism which gives back to the depositor the excess BNB.
