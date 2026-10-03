---
id: 25322
severity: "Medium"
---

# fundLoan() can be DoSed if returnFunds() is called before it.

## Description

It's possible to stop loans from being funded by calling returnFunds(). Exploit scenario

- attacker sees fundLoan(...) transaction and calls returnFunds(...) with an arbitrary amount
- returnFunds(...) increases [_drawableFunds](<https://github.com/maple-labs/fixed-term-loan-private/blob/670e9fe6dea857c8a0b203893fb32b66018f87d8/contracts/MapleLoan.sol#L237>)
- fundLoan(...) overrides _drawableFunds, which means that the amount sent earlier will be unaccounted
- the [require](<https://github.com/maple-labs/fixed-term-loan-private/blob/670e9fe6dea857c8a0b203893fb32b66018f87d8/contracts/MapleLoan.sol#L355>) that there are 0 unaccounted funds fails and the transaction reverts The lenders have incentive to do this if they want to withdraw and a loan would remove liquidity, see [getRedeemableAmounts(...)](<https://github.com/maple-labs/withdrawal-manager-private/blob/25d9ff308626d00831cd15e1829e4c2ea9365a0d/contracts/WithdrawalManager.sol#L337>).

## Proof of Concept

No PoC provided.

## Recommendation

In fundLoan(...), increase _drawableFunds instead of setting it.
