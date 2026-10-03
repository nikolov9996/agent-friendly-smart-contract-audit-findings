---
id: 25697
severity: "Medium"
---

# Incompatibility of Upgradeability Pattern in TitlesGraph Contract

## Description



## Proof of Concept

## Vulnerability Detail

In the `TitlesCore` contract, `TitlesGraph` is instantiated directly using a constructor rather than being set up as a proxy. This could lead to unexpected behavior when attempting to upgrade the contract, as the proxy would not have access to the initialized state variables or might interact incorrectly with uninitialized storage.

## Impact

Inability to leverage the upgradeability.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-titles/blob/main/wallflower-contract-v2/src/TitlesCore.sol#L44-L49](<https://github.com/sherlock-audit/2024-04-titles/blob/main/wallflower-contract-v2/src/TitlesCore.sol#L44-L49>)

```solidity
graph = new TitlesGraph(address(this), msg.sender);
```

## Recommendation

Deploy the `TitlesGraph` contract without initializing state in the constructor. Deploy a proxy that points to the deployed `TitlesGraph` implementation. Correct approach using a proxy pattern for upgradeable contracts:

```solidity
address graphImplementation = address(new TitlesGraph());
graph = TitlesGraph(payable(LibClone.deployERC1967(graphImplementation)));
graph.initialize(address(this), msg.sender);
```
