---
id: 25556
severity: "Low/Info"
---

# Using transfer() instead of call() may revert

## Description

When withdrawing ETH in OstiumPriceUpKeep::withdrawEth() using the deprecated transfer() function will make the transaction revert when:

1. The claimer smart contract does not implement a payable function.
2. The claimer smart contract does implement a payable fallback which uses more than 2300 gas units.
3. The claimer smart contract implements a payable fallback function that needs less than 2300 gas units but is called through proxy, raising the call's gas usage above 2300. Additionally, using higher than 2300 gas might be mandatory for some multisig wallets.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
Use sendValue() or: payable(msg.sender).call{value: amount}("");
```
