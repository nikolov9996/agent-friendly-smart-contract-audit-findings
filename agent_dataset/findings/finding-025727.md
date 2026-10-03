---
id: 25727
severity: "Low/Info"
---

# RiskHelper::isoGroup() returns 0, regardless of the passed subaccount

## Description

RiskHelper::isoGroup() is called in various functions across the code such as

```solidity
RiskHelper::canTrade(), SpotEngine::socializeSubaccount(), PerpEngine::socializeSubaccount(), ClearinghouseLiq::_assertLiquidationAmount(), ClearinghouseLiq::_assertCanLiquidateLiability(),
```

[ClearinghouseLiq::_finalizeSubaccount()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/ClearinghouseLiq.sol#L385>), and [ClearinghouseLiq_settlePositivePerpPnl()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/ClearinghouseLiq.sol#L521>).

However, it always returns 0 regardless of its parameter subaccount.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the functionality (currently commented out) or fully remove this function.
