---
id: 25064
severity: "Medium"
---

# IDOPoolAbstract::withdrawSpareIDO() does not take into account that several rounds may use the same IdoToken

## Description

`IDOPoolAbstract::withdrawSpareIDO()` checks if `contractBal >= ido.idoSize`, where `contractBal = IERC20(ido.idoToken).balanceOf(address(this))`. When several rounds use the same `ido.idoToken`, this check is incomplete as `ido.idoSize` only tracks the tokens of one round.

## Proof of Concept

No PoC provided.

## Recommendation

The correct check is withdrawing `contractBal - globalTokenAllocPerIDORound[idoConfig.idoToken]`, correctly tracking excess tokens.
