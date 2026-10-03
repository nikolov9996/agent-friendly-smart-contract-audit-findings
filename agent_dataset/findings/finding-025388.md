---
id: 25388
severity: "Low/Info"
---

# Ownable2Step should be preferred over Ownable

## Description

[Ownable](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L15C59-L15C71>) performs a simple ownership transfer by setting the owner to a new address.

This is dangerous and could result in an invalid owner being set. [Ownable2Step](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable2Step.sol>) performs additional checks by setting a pending owner which has then to accept the ownership.

Consider using it instead.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
