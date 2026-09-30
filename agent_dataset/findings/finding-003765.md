---
id: 3765
severity: "High"
---

# Users can refund before the sale has ended

## Description

The function claimRefund allows a user to claim a refund if the drop was not successful. The problem occurs because of incorrect inequality checks that allow a user to refund while purchases of said drop are still possible.
```solidity
function claimRefund(uint256 dropId, uint256[] calldata wrappedTokenIds) external {
    Drop memory drop = _drops[dropId];
    uint256 dropStartTokenId = dropToStartTokenId[dropId];
    if (drop.tokensSold >= drop.minSellOutTokens) {
        _revert(RefundNotAvailable.selector);
    }
    if (block.timestamp < drop.saleEndTime) {
        _revert(RefundNotAvailable.selector);
    }
```
Let's focus on the last if statement, if the timestamp is equal to the end time then the logic execution continues. This is an error because at the time block.timestamp == drop.saleEndTime the drop is still live and allows users to make purchases of the drop. We can observe this from the snippet below from the purchaseDrop function
```solidity
if (block.timestamp > drop.saleEndTime)
    _revert(SaleEnded.selector);
```
as we can see there is a time period where block.timestamp == drop.saleEndTime that allows both refunding and purchasing of the drop.

## Proof of Concept

no poc

## Recommendation

```solidity
if (block.timestamp <= drop.saleEndTime) {
    _revert(RefundNotAvailable.selector);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one time‑boundary error in the refund logic of a token sale contract. The contract is supposed to allow users to claim a refund only after the sale has ended and the minimum sell‑out threshold has not been reached. However, the claimRefund function checks the sale end condition with a strict less‑than comparison (block.timestamp < drop.saleEndTime). Because the purchaseDrop function only rejects purchases when the timestamp is greater than the end time (block.timestamp > drop.saleEndTime), there exists a single moment—when block.timestamp is exactly equal to drop.saleEndTime—where both refunding and purchasing are permitted. An attacker can trigger claimRefund at that exact timestamp, receive a refund for previously purchased tokens, and still be able to buy additional tokens in the same block or subsequent blocks before the sale is finally closed. This results in a loss of funds for the protocol, double‑spending of the sale inventory, and a breach of the intended accounting guarantees that refunds are only possible for failed sales. The issue manifests only at the precise boundary of the sale end time, making it difficult to detect during normal testing because blockchain timestamps are coarse and can vary by a few seconds, masking the exclusive‑inclusive mismatch. It was discovered during a manual audit that examined the conditional logic of both claimRefund and purchaseDrop and identified the contradictory inequality operators. From a user’s perspective the symptom is that a refund can be claimed while the UI still shows the sale as active, leading to unexpected zero balances after a refund and the ability to repurchase tokens without paying again. The bug belongs to the class of “time‑window boundary” or “off‑by‑one” logic errors that violate business rules about when certain actions are allowed. To remediate, the refund check should be changed to block.timestamp <= drop.saleEndTime (or the inverse logic using >=) so that refunds are blocked for the entire duration that purchases are still possible, thereby aligning the two functions and restoring the intended economic model.
