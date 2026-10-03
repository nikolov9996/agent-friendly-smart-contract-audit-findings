---
id: 25524
severity: "Low/Info"
---

# Faulty revert reason decoding in Delegatable

## Description

Delegatable decodes the revert reason of a revert in a way that may fail. It [adds](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/abstract/Delegatable.sol#L41-L45>) 4 bytes to the result pointer, which may mess up the length of the result variable, see more details [here](<https://github.com/sherlock-audit/2023-02-gmx-judging/issues/119>).

## Proof of Concept

No PoC provided.

## Recommendation

Don't decode the reason.
