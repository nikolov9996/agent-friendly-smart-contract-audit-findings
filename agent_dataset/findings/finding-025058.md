---
id: 25058
severity: "Low/Info"
---

# Null transfers in IDOPoolAbstract::_depositToTreasury() could be skipped

## Description

`IDOPoolAbstract::_depositToTreasury()` transfers `pos.fyAmount` and `pos.amount - pos.fyAmount`, but one of them may be `0` if the account only used `buyTokens` or `fyTokens`. Thus, if one of these 2 amounts is null, the transfer can be skipped. This can be relevant depending on the token used, as some revert on null transfers.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
function _depositToTreasury(uint32 idoRoundId, IDOStructs.Position memory pos) internal {
    IDOStructs.IDORoundConfig storage ido = idoRoundConfigs[idoRoundId];
    if (pos.fyAmount > 0) TokenTransfer._transferToken(ido.fyToken, treasury, pos.fyAmount);
    if (pos.amount - pos.fyAmount > 0) TokenTransfer._transferToken(ido.buyToken, treasury, pos.amount - pos.fyAmount);
}
```
