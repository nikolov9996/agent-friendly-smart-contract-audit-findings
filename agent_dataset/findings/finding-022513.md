---
id: 22513
severity: "High"
---

# swapValidatorDetails incorrectly writes keys

## Description

When loading BLS public keys from storage to memory, the keys are partly overwritten with zero bytes. This ultimately causes allocations of these malformed public keys to permanently lock deposited ETH in the beacon chain deposit contract.
ValidatorDetails.swapValidatorDetails is used by RioLRTOperatorRegistry.reportOutOfOrderValidatorExits to swap the details in storage of validators which have been exited out of order:
```solidity
VALIDATOR_DETAILS_POSITION.swapValidatorDetails(operatorId, fromIndex, validators.exited, validatorCount);
```
In swapValidatorDetails, for each swap to occur, we load two keys into memory from storage:
```solidity
keyOffset1 = position.computeStorageKeyOffset(operatorId, startIndex1);
keyOffset2 = position.computeStorageKeyOffset(operatorId, startIndex2);
assembly {
    // Load key1 into memory
    let _part1 := sload(keyOffset1) // Load bytes 0..31
    let _part2 := sload(add(keyOffset1, 1)) // Load bytes 32..47
    mstore(add(key1, 0x20), _part1) // Store bytes 0..31
    mstore(add(key1, 0x30), shr(128, _part2)) // Store bytes 16..47
    isEmpty := iszero(or(_part1, _part2)) // Store if key1 is empty
    // Load key2 into memory
    _part1 := sload(keyOffset2) // Load bytes 0..31
    _part2 := sload(add(keyOffset2, 1)) // Load bytes 32..47
    mstore(add(key2, 0x20), _part1) // Store bytes 0..31
    mstore(add(key2, 0x30), shr(128, _part2)) // Store bytes 16..47
    isEmpty := or(isEmpty, iszero(or(_part1, _part2))) // Store if key1 or key2 is empty
}
```
The problem here is that when we store the keys in memory, they don't end up as intended. Let's look at how it works to see where it goes wrong.
The keys used here are BLS public keys, with a length of 48 bytes, e.g.:
0x95cfcb859956953f9834f8b14cdaa939e472a2b5d0471addbe490b97ed99c6eb8af94bc3ba4d4bfa93d087
As such, previously to entering this for loop, we initialize key1 and key2 in memory as 48 byte arrays:
```solidity
bytes memory key1 = new bytes(48);
bytes memory key2 = new bytes(48);
```
Since they're longer than 32 bytes, they have to be stored in two separate storage slots, thus we do two sloads per key to retrieve _part1 and _part2, containing the first 32 bytes and the last 16 bytes respectively.
The following lines are used with the intention of storing the key in two separate memory slots, similarly to how they're stored in storage:
```solidity
mstore(add(key1, 0x20), _part1) // Store bytes 0..31
mstore(add(key1, 0x30), shr(128, _part2)) // Store bytes 16..47
```
The problem however is that the second mstore shifts _part2 128 bits to the right, causing the leftmost 128 bits to zeroed. Since this mstore is applied only 16 (0x10) bytes after the first mstore, we overwrite bytes 16..31 with zero bytes. We can test this in chisel to prove it:
Using this example key:
0x95cfcb859956953f9834f8b14cdaa939e472a2b5d0471addbe490b97ed99c6eb8af94bc3ba4d4bfa93d087
We assign the first 32 bytes to _part1:
```solidity
bytes32 _part1 = 0x95cfcb859956953f9834f8b14cdaa939e472a2b5d0471addbe490b97ed99c6eb
```
We assign the last 16 bytes to _part2:
```solidity
bytes32 _part2 = bytes32(bytes16(0x8af94bc3ba4d4bfa93d087d522e4b78d))
```
We assign 48 bytes in memory for key1:
```solidity
bytes memory key1 = new bytes(48);
```
And we run the following snippet from swapValidatorDetails in chisel:
```solidity
assembly {
    mstore(add(key1, 0x20), _part1) // Store bytes 0..31
    mstore(add(key1, 0x30), shr(128, _part2)) // Store bytes 16..47
}
```
Now we can check the resulting memory using !memdump, which outputs the following:
```
!memdump
[0x00:0x20]: 0x0000000000000000000000000000000000000000000000000000000000000000
[0x20:0x40]: 0x0000000000000000000000000000000000000000000000000000000000000000
[0x40:0x60]: 0x00000000000000000000000000000000000000000000000000000000000000e0
[0x60:0x80]: 0x0000000000000000000000000000000000000000000000000000000000000000
[0x80:0xa0]: 0x0000000000000000000000000000000000000000000000000000000000000030
[0xa0:0xc0]: 0x95cfcb859956953f9834f8b14cdaa93900000000000000000000000000000000
[0xc0:0xe0]: 0x8af94bc3ba4d4bfa93d087d522e4b78d00000000000000000000000000000000
```
We can see from the memory that at the free memory pointer, the length of key1 is defined 48 bytes (0x30), and following it is the resulting key with 16 bytes zeroed in the middle of the key.
Whenever we swapValidatorDetails using reportOutOfOrderValidatorExits, both sets of validators will have broken public keys and when allocated to will cause ETH to be permanently locked in the beacon deposit contract.
We can see how this manifests in allocateETHDeposits where we retrieve the public keys for allocations:
```solidity
// Load the allocated validator details from storage and update the deposited validator count.
(pubKeyBatch, signatureBatch) = ValidatorDetails.allocateMemory(newDepositAllocation);
VALIDATOR_DETAILS_POSITION.loadValidatorDetails(
    operatorId, validators.deposited, newDepositAllocation, pubKeyBatch, signatureBatch, 0
);
...
allocations[allocationIndex] = OperatorETHAllocation(operator.delegator, newDepositAllocation, pubKeyBatch, signatureBatch);
```
We then use the public keys to stakeETH:
```solidity
(uint256 depositsAllocated, IRioLRTOperatorRegistry.OperatorETHAllocation[] memory allocations) = operatorRegistry.allocateETHDeposits(depositCount);
depositAmount = depositsAllocated * ETH_DEPOSIT_SIZE;
for (uint256 i = 0; i < allocations.length; ++i) {
    uint256 deposits = allocations[i].deposits;
    IRioLRTOperatorDelegator(allocations[i].delegator).stakeETH{value: deposits * ETH_DEPOSIT_SIZE}(
        deposits, allocations[i].pubKeyBatch, allocations[i].signatureBatch
    );
}
```
Ultimately for each allocation, the public key is passed to the beacon DepositContract.deposit where it deposits to a public key for which we don't have the associated private key and thus can never withdraw.

## Proof of Concept

no poc

## Recommendation

We can solve this by simply mstoring _part2 prior to mstoring _part1, allowing the mstore of _part1 to overwrite the zero bytes from _part2:
```solidity
mstore(add(key1, 0x30), shr(128, _part2)) // Store bytes 16..47
mstore(add(key1, 0x20), _part1) // Store bytes 0..31
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a data‑corruption bug that occurs when the contract copies a 48‑byte BLS public key from storage into memory during a validator‑detail swap. The code loads the first 32 bytes and the last 16 bytes of the key into two temporary variables and then writes them into a newly allocated 48‑byte memory array using two mstore instructions. Because the second mstore writes at offset 0x30 (16 bytes after the start of the array) and applies a right‑shift of 128 bits, it overwrites the middle 16 bytes of the first part with zeros. As a result the reconstructed key contains a block of zero bytes in the centre, producing a malformed public key. This malformed key is later used by allocateETHDeposits and ultimately passed to the beacon DepositContract.deposit function. Since the public key does not correspond to any private key, the deposited ETH becomes permanently locked and can never be withdrawn. The bug is triggered whenever RioLRTOperatorRegistry.reportOutOfOrderValidatorExits calls ValidatorDetails.swapValidatorDetails, i.e., when validators are exited out of order. All operators, delegators and users who rely on the deposit mechanism are affected because their ETH disappears from their balance even though the transaction appears successful. The issue was discovered during a manual audit by inspecting the assembly implementation and confirming the memory layout with a chisel memory dump, which revealed the unexpected zeroed segment. It is hard to notice because the length field of the byte array remains correct (48 bytes) and the transaction does not revert; only the hidden zero bytes break the cryptographic key. Conceptually, the bug belongs to the class of incorrect memory layout or overlapping store errors for multi‑slot data structures. To fix the problem the two parts of the key must be stored in the correct order without overlapping, for example by writing the second part first and then the first part, or by adjusting the offsets so that the second mstore does not overwrite bytes written by the first. Properly reconstructing the full 48‑byte key restores the ability to withdraw deposited ETH and aligns the implementation with the intended business logic of staking and later redemption.
