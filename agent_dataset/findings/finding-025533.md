---
id: 25533
severity: "Low/Info"
---

# OstiumLinkUpKeep:topUp() is missing a length check for registryAddresses

## Description

```solidity
OstiumLinkUpKeep:topUp() checks if (upkeepIDs.length != topUpAmounts.length)
revert WrongParams();, but does not include the length of registryAddresses, which is
```

expected to be equal, as seen in [OstiumLinkUpKeep:getUnderfundedUpkeeps()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L45>).

## Proof of Concept

No PoC provided.

## Recommendation

Either do:

```solidity
if (upkeepIDs.length != topUpAmounts.length && topUpAmounts.length != registryAddresses.length) revert WrongParams();
```

or use an array of structs containing the 3 parameters.
