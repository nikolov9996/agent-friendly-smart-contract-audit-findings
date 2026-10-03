---
id: 25674
severity: "Medium"
---

# FlashRolloverLoan_G5 will not work for certain tokens due to not setting the approval to 0 after repaying a loan

## Description



## Proof of Concept

## Vulnerability Detail

Some `ERC20` tokens must have 0 approval before setting an approval to a non 0 amount, such as USDC.

The interest rises with `block.timestamp`, so borrowers will likely take a flash loan slightly bigger than `_repayAmount` to take this into account, or `repay` will fail.

Thus, when the approval is set for `TellerV2` of the `_principalToken`, `principal + interest` may be less than the approval, which will leave a dust approval.

`FlashRolloverLoan_G5::executeOperation()` later on approves `POOL`, which will revert as a dust amount was left.

## Impact

`FlashRolloverLoan_G5` will not work and be DoSed.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/FlashRolloverLoan_G5.sol#L243-L245](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/FlashRolloverLoan_G5.sol#L243-L245>) [https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/FlashRolloverLoan_G5.sol#L194-L196](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/FlashRolloverLoan_G5.sol#L194-L196>)

## Recommendation

Set the approval to 0 after repaying the loan.
