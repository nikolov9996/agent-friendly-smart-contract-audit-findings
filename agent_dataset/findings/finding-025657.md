---
id: 25657
severity: "Medium"
---

# A malicious operator will control consensus without risking stake (stake-exit lag exploit)

## Description



## Proof of Concept

## Impact

The network suffers a complete compromise of its security model. The malicious operator can perform any validator action (such as approving invalid transactions or censoring valid ones) without having any stake at risk of being slashed. This fundamentally breaks the economic security assumptions of the protocol, which relies on validators having skin in the game to behave honestly.

## Recommendation

Redesign the `commitValSetHeader` function to be internal (`_commitValSetHeader`), and create a new public function that handles both setting the signature verifier (optional) and committing the header in a single atomic transaction.

Alternatively apply `checkPermission` to `commitValSetHeader` so it can only be executed by the Network's relay service.
