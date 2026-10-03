---
id: 25439
severity: "Crit/High"
---

# Malicious path can be passed to redeem/withdraw() allowing an attacker to draing the strategy

## Description

path is not validated in redeem/withdraw(), which could lead to problems as the flow should always sell and buy the same token. Note: if a reentrant token is passed in the path it may be possible to deposit in the LoopStrategy while swapping, which would lead to stolen funds as the ratio would be higher due to having burned the shares but the assets are still in the strategy.

Note2: if ankrFlow is reentrant it could also be used to drain the funds. For example, consider this path:

```solidity
- attacker creates a pool of wFlow/reentrantToken and ankrFlow/reentrantToken;
- attacker deposits large amount of funds in the LoopStrategy;
```

- attacker withdraws using the following path:
- ankrFlow -> reentrantToken
- reentrantToken -> wFlow;
- whilst swapping, the reentrantToken allows the attacker to reenter the strategy and deposit. This deposit will give inflated shares as the _withdraw() method burns the shares first, but only withdraws all the assets by the end (the vault, for example);
- the attacker withdraws the inflated shares for much more funds.

## Proof of Concept

No PoC provided.

## Recommendation

Do not allow arbitrary paths.
