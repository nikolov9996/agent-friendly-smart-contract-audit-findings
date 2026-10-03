---
id: 25507
severity: "Low/Info"
---

# Storage variables can be cached to save gas

## Description

Reading/writing from the same storage variable more than once should be avoided to save gas.

## Proof of Concept

No PoC provided.

## Recommendation

BRC20Factory::burn() can cache the [fee](<https://github.com/orangecryptohq/orange-bridge-contract/blob/main/src/BRC20Factory.sol#L111>) (read twice). Vault::deposit() cache the [fee](<https://github.com/orangecryptohq/orange-bridge-contract/blob/main/src/Vault.sol#L84-L89>) (read thrice).

Vault::acceptAdmin() can cache the [pendingAdmin](<https://github.com/orangecryptohq/orange-bridge-contract/blob/main/src/Vault.sol#L153-L156>) (read 4 times). Vault::withdraw() can cache [signers.length](<https://github.com/orangecryptohq/orange-bridge-contract/blob/main/src/Vault.sol#L115>) (read number of signers times).
