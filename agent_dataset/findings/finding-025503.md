---
id: 25503
severity: "Low/Info"
---

# Ownership in BRC20Factory could be transferred using a 2 step procedure, similarly to Vault

## Description

It's recommended to change owner using a 2 step procedure to mitigate the risk of the contract losing ownership due to incorrect address.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the 2 step ownership transfer procedure with a pendingOnwer variable and acceptOwnership() function. [Here](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable2Step.sol>) is an example implementation.
