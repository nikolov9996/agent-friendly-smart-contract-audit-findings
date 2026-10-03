---
id: 25192
severity: "Low/Info"
---

# In BaseRouter, _handleSwapAction(...), users shouldn't be allowed to send funds to an allowed flasher

## Description

_handleSwapAction(...) allows sending funds to the Flasher. This should be to pay for a taken flashloan. However, if the goal of this exception is only to enable the payment of a flashloan, it should be removed and handled differently.

This is because it may allow users to send funds to the flasher, without taking a flashloan, either maliciously or by mistake.

## Proof of Concept

No PoC provided.

## Recommendation

Create a new action called repayFlashLoan and use it to repay the flashLoan. This action should revert if the amount being repaid is bigger than the flashloan taken.
