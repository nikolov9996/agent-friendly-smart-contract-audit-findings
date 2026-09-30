---
id: 3210
severity: "High"
---

# makePayment doesn't properly update stack, so most payments don't pay off debt

## Description

As we loop through individual payment in _makePayment, each is called with:  
```solidity
(newStack, spent) = _payment(
    s,
    stack,
    uint8(i),
    totalCapitalAvailable,
    address(msg.sender)
);
```
This call returns the updated stack as newStack but then uses the function argument stack again in the next iteration of the loop. The newStack value is unused until the final iterate, when it is passed along to _updateCollateralStateHash(). loans have actually had payments made against them.

## Proof of Concept

no poc

## Recommendation

```solidity
uint256 n = stack.length;
newStack = stack;
for (uint256 i; i < n; ) {
    (newStack, spent) = _payment(
        s,
        newStack,
        uint8(i),
        totalCapitalAvailable,
        address(msg.sender)
    );
```
This fixes the issue above, but the solution must also take into account the fix for the loop within _payment outlined here in Issue 134. If you follow the suggestion in that issue, then this function should return an extra value (elementRemoved) and use that to dictate whether the loop iterates forward, or remains at the same i for the next run. The final result should look like:
```solidity
function _makePayment(
    LienStorage storage s,
    Stack[] calldata stack,
    uint256 totalCapitalAvailable
) internal returns (Stack[] memory newStack, uint256 spent) {
    newStack = stack;
    bool elementRemoved = false;
    for (uint256 i; i < newStack.length; ) {
        (newStack, spent, elementRemoved) = _payment(
            s,
            newStack,
            uint8(i),
            totalCapitalAvailable,
            address(msg.sender)
        );
        totalCapitalAvailable -= spent;
        // if stack is updated, we need to stay at the current index
        // to process the new element on the same index.
        if (!elementRemoved) unchecked { ++i };
    }
    _updateCollateralStateHash(s, stack[0].lien.collateralId, newStack);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the batch payment routine that iterates over a list of loan entries (referred to as a stack) and attempts to apply a payment to each entry. In each loop iteration the code calls an internal function that returns an updated version of the stack (newStack) together with the amount actually spent. However, the loop continues to use the original stack variable for the next iteration instead of the freshly returned newStack. As a result, only the first loan in the batch receives the payment, while the remaining loans are processed against an unchanged snapshot of the stack, meaning their balances are never reduced. This stale‑reference bug is a classic state‑update error where mutable data is not propagated correctly across loop iterations. The issue manifests whenever a user or a contract invokes the batch payment function with more than one loan entry; the transaction will appear successful on‑chain, the event logs will indicate that payments were made, but the accounting state for most loans will remain unchanged. From the user’s perspective the UI shows a successful payment transaction, yet the loan balance displayed after the call is still the original amount, leading to confusion, potential collateral liquidation, and loss of capital because the protocol believes the debt is still outstanding. The bug was discovered during a manual security audit that examined the control flow of the _makePayment function and identified that the returned newStack value was never fed back into the loop. It can be hard to notice because the contract does not revert or emit an explicit error; the only symptom is a mismatch between expected and actual loan balances. The flaw violates fundamental accounting assumptions that each payment must decrement the corresponding debt and update the collateral state accordingly. To remediate the issue the loop must be rewritten to assign the returned newStack back to the variable used for the next iteration, and the loop index logic must be adjusted to handle cases where the _payment function removes an element from the stack (as described in a related issue). In conceptual terms the fix requires propagating the updated state after each iteration and ensuring the iteration counter reflects any structural changes to the collection being processed.
