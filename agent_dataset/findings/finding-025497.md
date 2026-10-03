---
id: 25497
severity: "Low/Info"
---

# BRC20Factory::addSigner() and Vault::addSigner() must not allow adding the zero address as a signer

## Description

The signature verification in BRC20Factory and Vault does not check that the recovered address is not null, which means that if address(0) is added as a signer, it would be possible to forge signatures.

## Proof of Concept

No PoC provided.

## Recommendation

In BRC20Factory::addSigner() and Vault::addSigner(), revert if an address(0) account is sent as argument.
