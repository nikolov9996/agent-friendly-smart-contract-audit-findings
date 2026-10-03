---
id: 25316
severity: "Low/Info"
---

# MapleLoan change the order of require to save on gas.

## Description

On open-term-loan/MapleLoan.sol, line 84 of acceptNewTerms(), there is a require to check that the refinance commitment according to the terms sent by the user is valid and to do so refinanceCommitment is loaded from storage. Then, on lines 88 and 89 additional checks are made regarding the arguments previously used.

## Proof of Concept

No PoC provided.

## Recommendation

If these checks were to be done before, in the case of invalid arguments, it would save gas by not having to load refinanceCommitment from storage.
