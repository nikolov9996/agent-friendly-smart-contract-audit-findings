---
id: 3479
severity: "High"
---

# Incorrect Token Transfer in _processERC20Payment() Function

## Description

The current design of the payment management within the SubExecutor contract introduces significant risks of logic failures in token transfer operations, potentially resulting in the inability to fulfill certain subscriptions and the potential locking of tokens.
The SubExecutor contract is designed to manage subscriptions and process automatic payments between accounts, using native/ERC20 tokens as a payment method. The current implementation presents an inconsistency in the authorization flow and execution of payments, specifically in the _processERC20Payment() function, which attempts to transfer ERC20 tokens from the SubExecutor contract to the initiator of the subscription using the transferFrom() method.

The payment functionality consists of the following steps:
1. Payment Processing processPayment() :
• This function is invoked by the initiator to process a payment based on an active subscription. The logic ensures that only the initiator can execute the payment, which is correct and desirable to control the flow of funds. It executes either _processERC20Payment() or _processNativePayment() whether it’s a native payment or ERC20.
2. ERC20 Token Transfer _processERC20Payment() :
• The use of transferFrom() implies that the initiator has permitted the SubExecutor to withdraw tokens on their behalf, which does not align with the subscription model where the SubExecutor is the holder of the funds and must send them directly to the initiator. This approach misinterprets the authorization dynamics in ERC20 contracts, leading to a potential failure in payment execution due to “insufficient allowance”.

## Proof of Concept

```solidity
function test_FuzzERC20Payment(uint256 tokenBalance, uint256 paymentAmount) public {
    // Ensure reasonable input values.
    vm.assume(tokenBalance >= 1 ether && tokenBalance <= 1000 ether);
    vm.assume(paymentAmount >= 1 wei && paymentAmount <= tokenBalance);
    // Mint tokens to SubExecutor and set the allowance for Initiator.
    vm.startPrank(deployer);
    token.mint(address(subExecutor), tokenBalance);
    vm.stopPrank();
    // SubExecutor approves Initiator to spend tokens on its behalf.
    vm.startPrank(address(subExecutor));
    token.approve(address(initiator), tokenBalance);
    vm.stopPrank();

    // Save initial balances of SubExecutor and Initiator for comparison later.
    uint256 subExecutorBalanceBefore = token.balanceOf(address(subExecutor));
    uint256 initiatorBalanceBefore = token.balanceOf(address(initiator));
    // Set up a subscription in SubExecutor for the Initiator.
    address owner = subExecutor.getOwner();
    uint256 validAfter = block.timestamp;
    uint256 validUntil = block.timestamp + 90 days;
    vm.startPrank(owner);
    subExecutor.createSubscription(address(initiator), paymentAmount, 30 days, validUntil, address(token));
    vm.stopPrank();
    // Warp time to meet the payment interval.
    vm.warp(validAfter + 30 days + 1);
    // Process the payment as the Initiator.
    vm.prank(address(initiator));
    subExecutor.processPayment();
    // Verify balances after payment.
    uint256 subExecutorBalanceAfter = token.balanceOf(address(subExecutor));
    uint256 initiatorBalanceAfter = token.balanceOf(address(initiator));
    // Assertions to verify the correct transfer of tokens.
    assertEq(subExecutorBalanceAfter, subExecutorBalanceBefore - paymentAmount, "SubExecutor's balance should decrease by the payment amount.");
    assertEq(initiatorBalanceAfter, initiatorBalanceBefore + paymentAmount, "Initiator's balance should increase by the payment amount.");
}
```
Currently, the test above reverts with ERC20: insufficient allowance.
Logs:
ERC20 Token balance of SubExecutor: 3617155993734787769
Allowance for Initiator to spend SubExecutor's tokens:

## Recommendation

Consider changing the code in the following way:
```solidity
- token.transferFrom(address(this), sub.initiator, sub.amount);
+ token.transfer(sub.initiator, sub.amount);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect use of the ERC20 allowance mechanism inside the SubExecutor contract's _processERC20Payment function. Instead of sending tokens that are already held by the SubExecutor to the subscription initiator, the code calls token.transferFrom(address(this), sub.initiator, sub.amount). This call assumes that the initiator has previously granted the SubExecutor an allowance to pull tokens from the initiator’s balance, which contradicts the intended subscription model where the SubExecutor is the token holder and must push the funds outward. Because no such allowance exists, the transferFrom call reverts with the standard ERC20 error "insufficient allowance", causing the payment transaction to fail. The failure occurs whenever processPayment is invoked for an ERC20‑based subscription, regardless of the contract’s token balance, and results in the initiator receiving no tokens while the SubExecutor’s balance remains unchanged. From a user perspective the UI may indicate that a payment was attempted, but the expected outcome – an increase in the initiator’s token balance – does not materialize; the user sees a zero or missing refund. This logic flaw can also be exploited by a malicious initiator who deliberately revokes any allowance, effectively locking the subscription payments and preventing the contract from fulfilling its obligations. The issue was uncovered during a security audit and reproduced with a fuzzing test that deliberately minted tokens to the SubExecutor, set up a subscription, and then observed the revert due to insufficient allowance. The bug is subtle because transferFrom is a common pattern for pulling funds, and developers may overlook that the direction of the transfer matters for the allowance model. The root cause is a misinterpretation of ERC20 authorization semantics, leading to a broken payment flow that violates the business rule that the contract must disburse funds it controls. The recommended remediation is to replace the transferFrom call with a direct token.transfer to the initiator, thereby aligning the code with the intended push‑payment model and eliminating the allowance requirement.
