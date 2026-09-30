---
id: 3764
severity: "High"
---

# Revert in closeSuccessfulDrop can cause tokens to be permanently stuck

## Description

The closeSuccessfulDrop function in the ColonyDropManager contract can fail due to an underflow in the payout calculation logic. This happens when the combined values of totalPaidOut and commissionFee exceed totalRaised. The failure results in a revert, making it impossible to close the drop and release funds. Without an emergency recovery mechanism, any tokens remaining in the contract will be permanently locked. Root Cause The vulnerability lies in the _handleCloseSuccesfulDropPayouts function. Specifically, the issue arises during the calculation of amountToSendToCreator: Vulnerable Code
```solidity
uint256 amountToSendToCreator = (totalRaised - _amountRaised.totalPaidOut)
- commissionFee;
```
If the sum of _amountRaised.totalPaidOut and commissionFee is greater than totalRaised, the subtraction causes an underflow. For instance: ). Assume: totalRaised = 600 totalPaidOut = 500 commissionFee = 120 (20% of totalRaised) *. The calculation for amountToSendToCreator becomes: amountToSendToCreator = (600 - 500) - 120; // -20% +. Since amountToSendToCreator is unsigned, this underflow triggers a revert.

## Proof of Concept

no poc

## Recommendation

Ensure that totalPaidOut and commissionFee do not exceed totalRaised before performing the calculation. For example:
```solidity
require(totalPaidOut + commissionFee <= totalRaised, "Invalid payout parameters");
```
Another way can be to modify the payout logic to prevent underflows:
```solidity
uint256 availableFunds = totalRaised > totalPaidOut ? totalRaised - totalPaidOut : 0;
uint256 amountToSendToCreator = availableFunds > commissionFee ? availableFunds - commissionFee : 0;
```
This ensures amountToSendToCreator never becomes negative.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic underflow in the payout routine of the closeSuccessfulDrop function of the ColonyDropManager contract. The code calculates the amount to send to the creator by subtracting the total amount already paid out and the commission fee from the total amount raised. If the sum of totalPaidOut and commissionFee exceeds totalRaised, the subtraction produces a negative result that, because the variable is unsigned, wraps around to a very large value and triggers a revert. This revert aborts the closeSuccessfulDrop execution, preventing the drop from being marked as closed and stopping any further transfers of the remaining tokens. The issue occurs only when the contract attempts to close a drop after more funds have been distributed than the original raise permits, a situation that can arise from rounding errors, multiple payout calls, or an incorrect commission calculation. From a user perspective the UI will show that the drop cannot be closed, the creator receives no additional payout, and contributors see no refund even though the contract still holds tokens. The funds remain locked in the contract because there is no emergency withdrawal path, effectively making the tokens permanently inaccessible. The bug was discovered during a manual audit of the payout logic, where the auditor identified that the subtraction was performed without a safety check. It is hard to notice because the revert only happens under specific numeric conditions that may not be exercised in normal test scenarios, and the failure appears as a generic transaction revert rather than a clear arithmetic error. Conceptually the flaw belongs to the class of unchecked arithmetic operations that can cause underflows and lock assets. The proper mitigation is to validate that totalPaidOut plus commissionFee does not exceed totalRaised before performing the subtraction, or to compute the available funds first and then subtract the commission only if sufficient balance remains. Adding a require statement or using a safe‑math style calculation eliminates the underflow, and introducing an emergency recovery function would allow the contract owner to retrieve any stuck tokens.
