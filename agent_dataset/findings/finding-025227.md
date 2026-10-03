---
id: 25227
severity: "Low/Info"
---

# Checks effects interactions pattern should always be used

## Description

The [checks-effects-interactions](<https://fravoll.github.io/solidity-patterns/checks_effects_interactions.html>) pattern should be used whenever possible, even if apparently it has no consequences. There are some instances specified in the relevant links where it isn't followed.

## Proof of Concept

No PoC provided.

## Recommendation

For example in withdraw() of glAVAX

```solidity
... // Transfer the user with the AVAX
payable(user).transfer(toWithdraw);
_updateWithdrawTotal(toWithdraw);
...
```

Should be instead

```solidity
... _updateWithdrawTotal(toWithdraw);
// Transfer the user with the AVAX
payable(user).transfer(toWithdraw);
...
```
