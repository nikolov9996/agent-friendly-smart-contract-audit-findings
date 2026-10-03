---
id: 25559
severity: "Low/Info"
---

# Unnecessary Typecasting of msg.sender

## Description

Unnecessary typecasting of msg.sender to address is seen on [L34](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumLinkUpKeep.sol#L34>) in OstiumLinkUpKeep::_onlyGov() and on [L32](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumRegistry.sol#L32>) in OstiumRegistry::_onlyGov().

This redundancy is unnecessary as msg.sender already returns an address.

## Proof of Concept

No PoC provided.

## Recommendation

To improve efficiency and clarity, remove the typecasting operation to save gas and eliminate confusion.
