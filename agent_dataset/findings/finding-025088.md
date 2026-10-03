---
id: 25088
severity: "Crit/High"
---

# BatchOut:executeBatchWithdrawFromStrategyWithSwap() gives unfairly different slippage depending on the chosen token

## Description

BatchOut:executeBatchWithdrawFromStrategyWithSwap() calls strategyRouter:withdrawFromStrategies() with the token having the [most requests](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/BatchOut.sol#L197>) shares.

This call will keep the assets/shares ratio, as it burns a number of shares according to the assets in strategyRouter:calculateSharesUsdValue().

However, the tokens actually withdrawn could be significantly less than the ideal corresponding to the shares. After withdrawing, it loops through the other tokens and calculates the ideal usd value from their requested shares.

This means that only the token with the max shares that was used to withdraw is taking the slippage, while the others are still getting their maximum usd value (slightly less as they will be swapped, incurring extra slippage).

Thus, users that chose to withdraw in the most requested token will likely incur significantly more slippage than the other tokens. The opposite scenario might also happen, if the withdrawToken has enough balance without going through swaps in router.withdrawFromStrategies(), then the slippage is taken only on the other tokens.

## Proof of Concept

No PoC provided.

## Recommendation

Consider creating cycles only of a certain withdrawal token, so users are under the same slippage. Else, a function could be created that handles withdrawals in several tokens, but this would take a much bigger effort.
