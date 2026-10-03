---
id: 25011
severity: "Crit/High"
---

# Malicious users can DOS the protocol by setting downsideProtected to a large value

## Description



## Proof of Concept

## Impact

Users are DOS'ed from interacting with the protocol so those who deposited have their assets frozen in the contract.

## Recommendation

Implement access control to updateDownsideProtected()
