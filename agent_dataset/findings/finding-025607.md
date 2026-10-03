---
id: 25607
severity: "Low/Info"
---

# Generating numbers smaller than P by doing % P might be vulnerable

## Description

```solidity
For example, in BaseInputBuilder::_bytifyToNoir()
_bytifyToNoir(address value) internal view returns (bytes32) {
    return bytes32(uint256(keccak256(abi.encode(value))) % _primeField);
}
```

1. the hashes are not unique, num A and num B = A + P will yield the same %
2. doing % P introduces a bias in the hash where smaller values are more frequent. This makes it easier to brute force solutions Thus, it may be possible (not sure about the required power) to specify a different address that leads to the same number supplief in the proof See this [writeup](<https://medium.com/aztec-protocol/vulnerabilities-found-in-aztec-2-0-9b80c8bf416c>), Bug: Generating prime field elements. Possible attack scenario: withdraw with a different address, leading to lost funds.

## Proof of Concept

No PoC provided.

## Recommendation

Use the Mimc254 contract to generate safer hashes.
