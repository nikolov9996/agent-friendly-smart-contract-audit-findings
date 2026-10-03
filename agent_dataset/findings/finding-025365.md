---
id: 25365
severity: "Low/Info"
---

# Duplicated slippage check in SyrupUserActions

## Description

SyrupUserActions::_swap() checks the slippage at the end `require(amountOut_ >= minAmountOut_, "SUA:S:INSUFFICIENT_AMOUNT_OUT");`. When the asset out is USDC, it double checks the slippage in SyrupUserActions::_swapDaiForUsdc() as `require(usdcOut_ >= minUsdcOut_, "SUA:SDU:INSUFFICIENT_AMOUNT_OUT");`.

## Proof of Concept

No PoC provided.

## Recommendation

There is no need to check the slippage in SyrupUserActions::_swapDaiForUsdc().
