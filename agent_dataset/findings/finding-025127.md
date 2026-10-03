---
id: 25127
severity: "Medium"
---

# Signatures missing some parameters being vulnerable to attackers using them coupled with malicious parameters

## Description



## Proof of Concept

[Here](<https://docs.biconomy.io/smartAccountsV2/bundler#bundler>) is how the biconomy bundler works (which is the same as the typical bundler):

> Aggregating userOps in an alternative mempool to normal Ethereum Transactions

Attacker can become a bundler and listen to the same mempool and perform the attack.

## Recommendation

Sign all parameters.
