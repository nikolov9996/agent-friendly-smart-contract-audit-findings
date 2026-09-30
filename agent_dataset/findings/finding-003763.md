---
id: 3763
severity: "High"
---

# Improper native token handling in matchBid and fulfillOrder causes transaction failures

## Description

The matchBid function in ColonyBidRouter.sol fails when the considerationToken specified in the order parameter is a native token (e.g., ETH). This occurs because the function attempts to interact with the IERC20 interface regardless of whether the token is native or ERC20-compliant:
```solidity
IERC20 considerationToken = IERC20(order.considerationToken);
considerationToken.approve(SEAPORT, bid.bidAmount);
ISeaport(SEAPORT).fulfillBasicOrder{value: msg.value}(order);
```
For native tokens, both the transferFrom and approve calls will fail because they are not applicable to ETH. This will result in a transaction revert whenever ETH is used as the considerationToken. Moreover, the fulfillOrder function in the SeaportProxy contract does not account for cases where the consideration token is the native token (e.g., ETH). This results in a failure when attempting to process such orders. The function uses the following logic to handle the consideration token:
```solidity
IERC20 considerationToken = IERC20(order.considerationToken);
considerationToken.approve(SEAPORT, totalConsiderationAmount);
ISeaport(SEAPORT).fulfillBasicOrder{value: msg.value}(order);
```
This implementation assumes the consideration token is an ERC20 token and attempts to call transferFrom and approve methods on it. However, if the considerationToken is the native token (e.g., ETH), these calls will fail because native tokens do not support the ERC20 interface. The issue leads to failed transactions whenever users attempt to fulfill an order with a native token as the consideration. This significantly limits the functionality of the fulfillOrder function and impacts usability.

## Proof of Concept

no poc

## Recommendation

```solidity
// Native token handling
if (msg.value < bid.bidAmount) {
    revert InsufficientEthSent();
}
ISeaport(SEAPORT).fulfillBasicOrder{value: bid.bidAmount}(order);
} else {
    // ERC20 token handling
    IERC20 considerationToken = IERC20(order.considerationToken);
    considerationToken.approve(SEAPORT, bid.bidAmount);
    ISeaport(SEAPORT).fulfillBasicOrder(order);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

An improper native token handling bug exists in the matchBid function of ColonyBidRouter.sol and the fulfillOrder function of SeaportProxy. Both functions treat the consideration token as an ERC20 token and unconditionally instantiate an IERC20 interface, then call approve (and implicitly rely on transferFrom) before invoking Seaport’s fulfillBasicOrder. When the order’s consideration token is the native blockchain token (e.g., ETH), the ERC20 interface does not exist, so the approve call reverts and the whole transaction fails. The bug is triggered whenever a user submits a bid or attempts to fulfill an order that specifies ETH as the token to be paid. From the user’s perspective the transaction simply reverts; no order is created, no funds are transferred, and the user only sees a failed transaction and loss of gas. The protocol’s accounting assumes that any consideration token can be approved and transferred via ERC20, which is violated for native tokens, breaking the expected refund or payment flow. The issue was discovered during a manual security audit that examined token handling paths and noticed that native‑token cases were not covered by any conditional logic. Because the code compiles and works for ERC20 tokens, the problem can be missed by standard unit tests that only use ERC20 assets. Exploitation does not require malicious intent; any honest user trying to use ETH will cause the revert, effectively a denial‑of‑service for native‑token orders. The impact is high because it prevents a whole class of orders, wastes gas, and may erode confidence in the marketplace. The proper fix is to add a branch that detects when order.considerationToken represents the native token, skips the ERC20 approve call, validates that msg.value is at least the required bid amount, and forwards that amount with the call to fulfillBasicOrder. This aligns the implementation with the business rule that native tokens are transferred via the call value rather than ERC20 approve/transfer mechanisms.
