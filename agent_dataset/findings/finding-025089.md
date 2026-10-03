---
id: 25089
severity: "Crit/High"
---

# Halted withdrawals in BatchOut due to setting withdrawTo to address(0) in scheduleWithdrawal()

## Description

BatchOut:scheduleWithdraw() allows sending a withdrawTo argument of 0. Some tokens, such as [USDT](<https://bscscan.com/address/0x55d398326f99059ff775485246999027b3197955#code>), revert when transferring tokens to address 0.

This means that, when fulfilling withdrawals, the loop will be DoSed when it reaches the 0 address withdrawal, halting all withdrawals in the cycle.

## Proof of Concept

No PoC provided.

## Recommendation

Do not allow 0 address withdrawTo.
