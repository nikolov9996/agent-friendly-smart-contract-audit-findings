---
id: 1924
severity: "High"
---

# stopLimit Id collision with bracket

## Description

High-severity vulnerability in Oku's dual-contract architecture where parallel order creation between StopLimit.sol and Bracket.sol enables order data corruption and potential double-refund exploitation through orderId collisions.
```solidity
// Current implementation
function generateOrderId(address user) external returns (uint96) {
    return uint96(uint256(keccak256(abi.encodePacked(
        block.number,
        user
    ))));
}
```
Deterministic orderId generation lacks contract-specific entropy, allowing cross-contract collisions within the same block.
Internal pre-conditions
1. Shared AutomationMaster instance between contracts
2. Mutable orders mapping in Bracket contract
3. Independent order creation flows
```solidity
mapping(uint96 => Order) public orders;
```
External pre-conditions
1. MEV capabilities (same-block execution)
2. Sufficient token balance for multiple orders
3. Active protocol state
Attack Path
```solidity
// Block N
// Step 1: Create Bracket order (5000 USDT)
bracket.createOrder({
    amountIn: 5000e6,
    recipient: attacker
});
// OrderId = hash(blockN + attacker)
// Same Block N
// Step 2: Create StopLimit order (10000 USDT)
stopLimit.createOrder({
    amountIn: 10000e6,
    recipient: attacker
});
// Internally calls bracket.fillStopLimitOrder
// Same OrderId = hash(blockN + attacker)
// Step 3: Cancel order twice
bracket.cancelOrder(orderId); // Refunds 10000 USDT
bracket.cancelOrder(orderId); // Refunds 10000 USDT again
```
• Double-spend vulnerability
• Order state corruption
• Accounting system compromise
• Direct financial loss

## Proof of Concept

no poc

## Recommendation

```solidity
contract AutomationMaster {
    // Add contract-specific entropy
    function generateOrderId(
        address user,
        address contractSource
    ) external returns (uint96) {
        return uint96(uint256(keccak256(abi.encodePacked(
            block.number,
            user,
            contractSource,
            _orderNonce++ // Additional entropy
        ))));
    }

    uint256 private _orderNonce;
}
```
```solidity
// Update in Bracket.sol
function createOrder(...) external {
    uint96 orderId = MASTER.generateOrderId(msg.sender, address(this));
    // Rest of the function
}
```
```solidity
// Update in StopLimit.sol
function createOrder(...) external {
    uint96 orderId = MASTER.generateOrderId(msg.sender, address(this));
    // Rest of the function
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an order identifier collision that occurs because both the StopLimit and Bracket contracts generate order IDs using a deterministic hash of only the current block number and the caller address. This hash provides no contract‑specific entropy, so when the same user creates orders in the two contracts within the same block, the resulting uint96 identifiers are identical. The root cause is the shared AutomationMaster function that lacks a per‑contract salt or a nonce, making the identifier predictable and repeatable across contracts. An attacker with MEV capabilities can exploit this by submitting a Bracket order and a StopLimit order in the same block, causing both to receive the same orderId. Because the Bracket contract stores orders in a mapping keyed by orderId, the StopLimit order later invokes the Bracket’s fill routine with the colliding identifier. When the attacker calls cancelOrder on the shared orderId, the Bracket contract processes the refund for the first order and, due to the collision, does not recognise that the order has already been settled. A second cancel call with the same identifier succeeds again, resulting in a double refund. The impact is a double‑spend of user funds, corruption of the protocol’s accounting state, and potential financial loss for the platform. The issue manifests only when two orders from the same address are created in the same block, a condition that can be orchestrated by an attacker who can control transaction ordering. All participants that rely on the order mapping – the protocol, its users, and any downstream contracts – are affected because the accounting invariants are broken. The flaw was discovered during a manual audit of the dual‑contract architecture, where the auditor noticed that the orderId generation did not incorporate any contract‑specific data. It is hard to notice because the identifier appears unique per user per block, and the mapping lookup succeeds, giving the illusion that the order is valid. The proper fix is to add contract address and a monotonically increasing nonce to the hash input, ensuring that each contract produces a distinct namespace for order IDs and that repeated calls cannot generate the same identifier. By separating the identifier space, the double‑refund path is eliminated and the accounting model remains sound. From a user perspective the symptom is that a refund may be received twice, balances may drop unexpectedly, or an order appears to be cancelled but still shows as active, contradicting the expectation that a single cancellation refunds the exact amount once.
