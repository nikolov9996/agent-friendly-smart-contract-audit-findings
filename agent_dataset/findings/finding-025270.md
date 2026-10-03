---
id: 25270
severity: "Medium"
---

# RsaVerifyOptimized sets the size of the key to 1024 bits, which is unsafe

## Description

RSA signatures rely on the size of the key for higher safety assurances. As computational power advances, it becomes possible to brute force signatures up to more bits.

[This](<https://www.rareskills.io/post/solidity-rsa-signatures-for-aidrops-and-presales-beating-ecdsa-and-merkle-trees-in-gas-efficiency>) article indicates keys up to 829 bits have been cracked, which is dangerously close to the hardcoded 1024 bits.

The original RsaVerifyOptimized repository [recommends](<https://github.com/adria0/SolRsaVerify/tree/master?tab=readme-ov-file#usage-with-openssl-openssl-311>) setting a key size of at least 2048 bits.

## Proof of Concept

No PoC provided.

## Recommendation

Update the key size to be 2048.
