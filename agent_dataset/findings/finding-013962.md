---
id: 13962
severity: "High"
---

# Specifying validatorIndex as uint64 allows BeaconProofsLib.validateValidatorProof() to pass with incorrect proofs

## Description

In BeaconProofsLib.validateValidatorProof(), validatorIndex is declared as uint64:
```solidity
function validateValidatorProof(
uint64 validatorIndex,
```
However, validatorIndex should be uint40 instead as the maximum length of validators in BeaconState is 2 ** 40. Any index greater than type(uint40).max is invalid.
This becomes a problem as validatorIndex is OR-ed with the other bits in index:
```solidity
uint256 index = (CONTAINER_IDX « (VALIDATOR_HEIGHT + 1)) | uint256(validatorIndex);
```
Assuming the rightmost bit in index is bit 0, an attacker can set bits 41 to 45 of validatorIndex to switch from the validators field to certain fields after it in BeaconState. You can think of it as modifying CONTAINER_IDX to a different value, which would end up proving a different field in BeaconState.
For example, assume CONTAINER_IDX = 15 and validatorIndex = 0. index would be:
(15 « (VALIDATOR_HEIGHT + 1)) | uint256(0) = 0x1e0000000000
The same value can be reached with CONTAINER_IDX = 12 and validatorIndex = 0x1e0000000000, since:
(12 « (VALIDATOR_HEIGHT + 1)) | uint256(0x1e0000000000) = 0x1e0000000000
If validateValidatorProof() was called with validatorIndex = 0x1e0000000000, the function would end up validating validatorFields against the field at index 15 in BeaconState, which is previous_epoch_participation.
This makes it possible for validateValidatorProof() to pass with an invalid validatorFields.

## Proof of Concept

no poc

## Recommendation

Declare validatorIndex as uint40 instead:
```solidity
function validateValidatorProof(
uint64 validatorIndex,
+ uint40 validatorIndex,
bytes32[] calldata validatorFields,
```
This change should be reflected throughout the codebase - any variable that represents the validator's index in the beacon chain should be changed to uint40:
• BeaconProofsLib.sol#L33-L34
• NativeVaultLib.sol#L20-L22
The unsafe cast from uint64 to uint40 at NativeVaultLib.sol#L120 can then be removed.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect data type used for the validator index in the proof‑verification routine of a beacon‑chain based restaking contract. The function validateValidatorProof expects a validatorIndex argument that is declared as a 64‑bit unsigned integer, even though the beacon state limits validator identifiers to 40 bits because the maximum number of validators is 2^40. The implementation builds a composite 256‑bit index by left‑shifting a container identifier and then OR‑ing the supplied validatorIndex. Because the validatorIndex can contain bits above the 40th position, an attacker can set those high bits to alter the effective container identifier embedded in the composite index. By carefully choosing a validatorIndex with bits 41‑45 set, the attacker can make the composite index point to a different field in the BeaconState than the one intended, for example causing the function to validate a proof against the previous_epoch_participation field while still presenting validatorFields that belong to a validator. This manipulation allows the proof verification to succeed with an otherwise invalid validatorFields payload. The impact is that any protocol component that relies on the correctness of these proofs – such as the NativeVault that locks and releases user funds based on validator proofs – can be tricked into accepting forged data, potentially leading to unauthorized withdrawals or incorrect accounting of staking rewards. The flaw manifests whenever validateValidatorProof is invoked with a caller‑controlled validatorIndex, which is possible through external calls that forward user‑supplied data. All participants that submit proofs, including regular users and the protocol itself, are affected because the verification step no longer guarantees the integrity of the underlying beacon data. The issue was discovered during a manual audit that compared the declared type against the protocol’s specification and examined the bitwise composition of the index, revealing that the extra bits could be used to tamper with the container identifier. It is subtle because the function appears to perform a straightforward bitwise operation and the overflow bits are not directly visible in the resulting index, making the bug easy to overlook in testing. The proper remediation is to restrict the validatorIndex to the correct 40‑bit size, i.e., declare it as uint40, propagate this change throughout the codebase, and eliminate any unsafe casts that truncate a larger integer to 40 bits. By enforcing the correct range, the composite index can no longer be forged, restoring the intended guarantee that validator proofs correspond to the exact validator field they claim to represent. From a user’s perspective the symptom would be that a proof that should be rejected is accepted, leading to unexpected behavior such as a vault releasing funds when no legitimate validator participation has occurred, or accounting entries showing participation where none exists. This class of bug is a range‑overflow or bit‑mask manipulation flaw, where an oversized integer is used in a bitwise composition, allowing an attacker to rewrite higher‑order bits and subvert logical checks.
