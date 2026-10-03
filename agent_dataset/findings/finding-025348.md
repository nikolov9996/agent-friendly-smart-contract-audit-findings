---
id: 25348
severity: "Medium"
---

# Pool Delegates can set an unreasonably large delegate management fee rate at anytime

## Description

Using the function setDelegateManagementFeeRate() the pool manager can set an unreasonably large delegateManagementFeeRate (all the way up to 100%) at any time, stopping payments from reaching the pool (i.e. the liquidity providers).

Since the loan manager updates the delegateManagementFeeRate every time a payment is made (and a new is added), this change will have an almost immediate impact, and the liquidity providers will have no choice but to accept these new terms.

Some of them could try to withdraw their funds, but the majority of them would not be allowed to do so since the loan had already been made and the funds were locked.

A pool delegate could therefore start by setting a low management fee to attract LPs to his pool and, after loans had been issued, this fee could be drastically increased without any governor or LPs permission, to the detriment of the LPs.

## Proof of Concept

No PoC provided.

## Recommendation

Allow the governor to limit this value or give the governor permission to accept or reject a change in the delegateManagementFeeRate. Alternatively, delegateManagementFeeRate could be set in deployment and not allowed to change, or at least stay constant on a per loan basis.
