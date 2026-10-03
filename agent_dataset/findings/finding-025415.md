---
id: 25415
severity: "Low/Info"
---

# _msgSender() is mixed with msg.sender

## Description

The code is using OpenZeppelin's Context contract which is intended to allow meta-transactions. It works by using a call to _msgSender() instead of querying msg.sender directly, because the method allows those special transactions.

The problem is that the bridge adapters use msg.sender directly instead of _msgSender(). While this doesn't significantly impact the functions [called](<https://github.com/0x73696d616f/evm-eol-3s-audit/blob/b545f6724c3f0b5eebea72c652d7f9728f1627f0/src/helpers/ccdm/CCDMHost.sol#L247>) from CCDMHost, as meta-transactions aren't needed there, it causes issues for users who call the adapters directly.

## Proof of Concept

No PoC provided.

## Recommendation

Change the code to use _msgSender() instead of msg.sender.
