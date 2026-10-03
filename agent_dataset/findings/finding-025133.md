---
id: 25133
severity: "Medium"
---

# Claiming will fail for Ole and D1MemeToken if the overfunded ETH reverts

## Description

FairLauncher::claims() reverts if the ETH claimed from overfunded presales fails. However, this means that Ole and D1MemeToken claiming will also revert, when this could be prevented.

## Proof of Concept

No PoC provided.

## Recommendation

Instead of reverting, the ETH could be sent to a protocol wallet and emit an event to refund users later. The likelihood of happening is low because the protocol expects its users to be EOAs or multisig wallets, which don't have this problem.
