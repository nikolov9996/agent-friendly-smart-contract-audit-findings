---
id: 25059
severity: "Crit/High"
---

# Funding cap in IDOPoolAbstract::_basicParticipationCheck() is imprecise and can lead to excessive tokens sold

## Description

`IdoTokens` are allocated in `IDOPoolAbstract::enableIDORound()` up to `idoConfig.idoSize`. The funding cap in `IDOPoolAbstract::_basicParticipationCheck()` is performed as `newFundedUSDValue <= idoConfig.idoSize  idoConfig.idoPrice`*, where `newFundedUSDValue == idoConfig.fundedUSDValue + amount `*` idoConfig.idoPrice`.

Firstly, `idoConfig.fundedUSDValue` has `fyToken` or `buyToken` units (see `IDOPoolAbstract::participateInRound()`), but it is summed to `amount * idoConfig.idoPrice`, which has different units as it is multiplied by the price.

Additionally, tokens are handed out according to `tokenAllocation = (amount * 10**idoConfig.idoTokenDecimals) / idoConfig.idoPrice`, but `newFundedUSDValue` is compared against `amount * idoConfig.idoPrice`, not taking into account the decimals.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
function participateInRound(...) {
    ...
    uint256 tokenAllocation = (amount * 10**idoConfig.idoTokenDecimals) / idoConfig.idoPrice;
    uint256 newTotalTokens = idoConfig.fundedUSDValue + tokenAllocation;
    require(newTotalTokens <= idoConfig.idoSize, "Funding cap exceeded");
}
```
