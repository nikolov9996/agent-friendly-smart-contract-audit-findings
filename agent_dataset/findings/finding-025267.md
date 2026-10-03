---
id: 25267
severity: "Medium"
---

# RsaVerifyOptimized::pkcs1Sha256() modified the original code incorrectly in one instance

## Description

RsaVerifyOptimized::pkcs1Sha256() [code](<https://github.com/adria0/SolRsaVerify/tree/master?tab=readme-ov-file#usage-with-openssl-openssl-311>) has slight changes to the original code.

[There](<https://github.com/Keyring-Network/core-v2/blob/master/src/lib/RsaVerifyOptimized.sol#L273>) is one modification that is different from the original, which is checking if the first bytes of decipher are 0x00 and 0x01, respectively.

As can be seen in the following code snippet, the first 2 bytes of decipher may be for example 0x0101 and it will not set the result to false.

```solidity
// if (decipher[0] != 0 || decipher[1] != 0x01) {
    // return false;
    // }
if iszero(and(mload(add(decipher, 32)), 0x0001ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)) {
    result := false
}
```

Additionally, here should be 111, but the code is not reachable as it only accepts digestAlgoWithParamLen == 17 == sha256ExplicitNullParamByteLen.

## Proof of Concept

No PoC provided.

## Recommendation

Use the previous optimized assembly code.
