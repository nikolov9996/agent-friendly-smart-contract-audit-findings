---
id: 25734
severity: "Crit/High"
---

# OffchainExchange::swapAmm() does not validate that txn.priceX18 > 0, allowing donation attacks

## Description

OffchainExchange::swapAmm() calculates the quote amount as -txn.amount.mul(txn.priceX18). Thus, if the price is negative, base and quote amount will have the same sign.

If it's negative, the transaction will revert as it would lead to a smaller k in the amm. However, if it's positive, it will provide both base and quote to the amm and the user will take a big loss. Using a txn.price < 0, it can be used to perform donation attacks, which could be dangerous, as it maintains the base/quote ratio but inflates lp value.

An example of an attack is the following: Price = 10, attacker mints 11 lp using 1 base and 10 quote. Attacker calls OffchainExchange::swapAmm() with txn.amount = 1e21 and txn.price = -10. This changes the amm state to 11 lp, approx 1e21 base and 1e22 quote.

Some user adds lp with 1e20 base and 1e21 quote (note that the price is maintained) toMint = 1e20/1e21*11, which rounds down to 0, stealing the funds.

Additionally, it is [recommended](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/ClearinghouseLiq.sol#L708>) to enforce that swaps follow the amm curve to prevent price manipulations.

## Proof of Concept

No PoC provided.

## Recommendation

Ensure that the price is positive, as a negative price would be a user mistake or a donation attack.
