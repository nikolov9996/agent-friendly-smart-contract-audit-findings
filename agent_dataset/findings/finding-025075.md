---
id: 25075
severity: "Low/Info"
---

# getDepositFeeInBNB() assumes a stablecoin price of 1 USD, which may not be true if it depegs

## Description

In Batch.sol, function [`getDepositFeeInBNB()`](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L185>) calculates the fee amount in BNB, considering that the stablecoin price is 1 USD, which may not be true, as we've seen with USDC in the past.

It also means that if a coin other than a stablecoin is used to deposit, a much smaller/larger fee would be triggered. For example, 20 tokens are deposited, the fee is 10%, so 2 fee amount. The token price is 10 USD. The bnb price is 250 USD. The fee amount in BNB would be 2/250 = 0.008.

So the user would deposit 20 tokens, worth 200 USD and pay a fee of 0.008 BNB or 2 USD, which is 2/200 = 1%, instead of 10%. The real fee, according to the code, is depositFee/(token price in USD).

## Proof of Concept

No PoC provided.

## Recommendation

Consider fetching the price of BNB in units of the to be deposited token. This way, the fee in the code will match the real percentage in USD.
