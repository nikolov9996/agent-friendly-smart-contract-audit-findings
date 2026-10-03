---
id: 25205
severity: "Low/Info"
---

# Saving parameters in memory without using them spends gas

## Description

In BaseVault.sol several functions receive a variable as a parameter then save it in memory and immediately use it to make a call without making any changes.

This is most likely done to increase readability however since there is no reason to save it in memory, this is spending unnecessary gas.

```solidity
function increaseAllowance(address receiver, uint256 shares) public
override returns (bool) {
    address operator = receiver;
    increaseWithdrawAllowance(operator, receiver, convertToAssets(shares));
    return true;
}
```

## Proof of Concept

No PoC provided.

## Recommendation

In the mentioned functions in the links, remove the variable in memory being created and pass the variable directly to the call. In the example above, address operator.
