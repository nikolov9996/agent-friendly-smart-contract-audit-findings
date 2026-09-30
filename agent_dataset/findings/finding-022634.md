---
id: 22634
severity: "High"
---

# Incorrect prefundingRefundcalculation will dis-

## Description

Incorrect prefundingRefund calculation will lead to underflow and hence disallowing claiming
The prefundingRefund variable calculation inside the claimProceeds function is incorrect
```solidity
function claimProceeds(
    uint96 lotId_,
    bytes calldata callbackData_
) external override nonReentrant {
    ...
    (uint96 purchased_, uint96 sold_, uint96 payoutSent_) = _getModuleForId(lotId_).claimProceeds(lotId_);
    ...
    // Refund any unused capacity and curator fees to the address dictated by the callbacks address
    // By this stage, a partial payout (if applicable) and curator fees have been paid, leaving only the payout amount (`totalOut`) remaining.
    uint96 prefundingRefund = routing.funding + payoutSent_ - sold_;
    unchecked {
        routing.funding -= prefundingRefund;
    }
```
Here sold is the total base quantity that has been sold to the bidders. Unlike required, the routing.funding variable need not be holding capacity + (0,curator fees) since it is decremented every time a payout of a bid is claimed
```solidity
function claimBids(uint96 lotId_, uint64[] calldata bidIds_) external override nonReentrant {
    ...
    if (bidClaim.payout > 0) {
        ...
        // Reduce funding by the payout amount
        unchecked {
            routing.funding -= bidClaim.payout;
        }
```
Example
Capacity = 100 prefunded, hence routing.funding == 100 initially Sold = 90 and no partial fill/curation All bidders claim before the claimProceed function is invoked Hence routing.funding = 100 - 90 == 10 When claimProceeds is invoked, underflow and revert:
uint96 prefundingRefund = routing.funding + payoutSent_ - sold_ == 10 + 0 - 90
Claim proceeds function is broken. Sellers won't be able to receive the proceedings

## Proof of Concept

no poc

## Recommendation

Change the calculation to:
```solidity
uint96 prefundingRefund = capacity - sold_ + curatorFeesAdjustment (how much was prefunded initially - how much will be sent out based on capacity - sold)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains an arithmetic error in the calculation of the prefundingRefund value inside the claimProceeds function. The code adds the current routing.funding balance to the amount already sent (payoutSent_) and then subtracts the total quantity sold (sold_). Because routing.funding is reduced each time a bid payout is claimed, it may already be lower than the sold amount when claimProceeds is finally executed. In that situation the expression routing.funding + payoutSent_ - sold_ becomes a negative number, but the variables are unsigned (uint96). The unchecked block then causes an under‑flow, wrapping the value to a very large number and triggering a revert when the subsequent subtraction routing.funding -= prefundingRefund is performed. The bug appears only when all bidders have claimed their payouts before the seller calls claimProceeds, which is a realistic execution order. As a result the seller’s transaction reverts, no proceeds are transferred, and the funds remain locked in the contract. Users see the expected payout disappear, the UI may show an error or simply no change in balance, and the seller receives nothing despite having sold assets. The issue was discovered during a manual audit that examined the state changes of routing.funding across claimBids and claimProceeds. It is hard to notice because the arithmetic looks correct in isolation and the unchecked block suppresses Solidity’s built‑in overflow checks. Conceptually the bug belongs to the class of unsigned integer under‑flow errors caused by incorrect accounting of prefunded capacity. The correct approach is to compute the refund based on the original prefunded capacity rather than the mutable routing.funding value, for example by using capacity - sold_ plus any curator‑fee adjustments. Fixing the calculation eliminates the under‑flow, restores the ability of sellers to claim proceeds, and preserves the intended accounting invariants of the protocol.
