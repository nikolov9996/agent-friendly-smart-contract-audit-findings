---
id: 25359
severity: "Low/Info"
---

# The basic strategy does not have slippage control when withdrawing which may lead to arbitrage

## Description

MapleBasicStrategy::withdrawFromStrategy() does not send an upper limit on the amount of shares minted, which means an unexpected loss may happen in case of slashing before the withdrawal from the EIR4626 vault. Although many vaults do not have slashing abilities (such as the one tested, SavingsUsds), some may do which can cause this issue.

## Proof of Concept

No PoC provided.

## Recommendation

Consider adding slippage control on a case by case basis.
