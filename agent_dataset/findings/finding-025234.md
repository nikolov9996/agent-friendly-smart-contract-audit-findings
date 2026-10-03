---
id: 25234
severity: "Low/Info"
---

# rebalance(), withdrawAmount needed from the ReservePool can be simplified

## Description

In function rebalance(), the withdrawAmount from the ReservePool can be computed inside the first if statement.

## Proof of Concept

No PoC provided.

## Recommendation

Change the code to

```solidity
function rebalance() external payable isRole(NETWORK_MANAGER) {
    ... uint256 withdrawAmount; // new if (balance > 0 && currentReserves < reserveTarget) {
        uint256 toFill = reserveTarget - currentReserves;
        uint256 toReserves = toFill > balance ? balance : toFill;
withdrawAmount = toFill - toReserves; // new
IGReservePool(reservePoolAddress).deposit(toReserves);
balance -= toReserves;
} else {
... }
```
