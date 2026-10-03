---
id: 25491
severity: "Medium"
---

# address.transfer is used in the codebase, which could lead to stuck funds

## Description

Using address.transfer is not recommended as future gas cost changes can make it no longer work or users might use smart contract wallets. The reason is that it only forwards 2300 gas, which can lead to the 2 problems mentioned before.

## Proof of Concept

No PoC provided.

## Recommendation

Use address.call{value: amount}("") instead, [here](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L33>) is an example implementation.

If the gas usage of the target is a concern, [this](<https://github.com/nomad-xyz/ExcessivelySafeCall/blob/main/src/ExcessivelySafeCall.sol#L24>) implementation can be used instead, setting the _gas to some amount that may be changed and _maxCopy and _calldata to 0.
