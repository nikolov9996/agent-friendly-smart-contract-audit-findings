---
id: 25201
severity: "Medium"
---

# Payback can be DoSed in the BorrowingVault, may be profitable for liquidators

## Description

The borrowing vault enables anyone to payback the debt of another user. Thus, attackers can frontrun a user payback transaction, payback 1 wei and stop users from paying back their debts. This would make sense for liquidators, who are incentivized to do this to liquidate users.

## Proof of Concept

[https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCPaybackDoSed.t.sol#L27](<https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCPaybackDoSed.t.sol#L27>)

## Recommendation

There are 2 alternatives:

- Instead of reverting if the payback is bigger than the maximum, limit it to the maximum.
- Only enable the user to payback its debt.
