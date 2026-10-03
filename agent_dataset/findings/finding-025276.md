---
id: 25276
severity: "Low/Info"
---

# Creating a new proposal in StandardGovernor may reach a state of permanent DoS

## Description

The function [StandardGovernor.propose](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/StandardGovernor.sol#L138-L162>) is used to create a new proposal to be executed in the StandardGovernor.

If it's the first proposal for that epoch, it will call [PowerToken.markNextVotingEpochAsActive](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/PowerToken.sol#L125-L143>) to set the next target supply. Inside this

```solidity
function, there's a check to cap the next target supply at type(uint240).max: uint240 nextTargetSupply_ = _nextTargetSupply = UIntMath.bound240( uint256(_targetSupply) + (_targetSupply *
```

participationInflation) / ONE ); The issue is that the most likely scenario will be that the multiplication _targetSupply * participationInflation will overflow first, before any bound checks.

Because _targetSupply is a uint240 and participationInflation is a uint16, the multiplication will raise a panic overflow when it passes the maximum value of a uint240.

This means that, in most cases, the transaction will revert with a panic overflow instead of just capping the next target supply. Because the problematic function is called by StandardGovernor.propose for the first proposal of an epoch, this results in a permanent denial-of-service situation where it will no longer be possible to create new proposals in the StandardGovernor.

## Proof of Concept

No PoC provided.

## Recommendation

Cast _targetSupply to not allow a uint240 overflow:

```solidity
uint240 nextTargetSupply_ = _nextTargetSupply = UIntMath.bound240( uint256(_targetSupply) + (uint256(_targetSupply) *
```

participationInflation) / ONE );
