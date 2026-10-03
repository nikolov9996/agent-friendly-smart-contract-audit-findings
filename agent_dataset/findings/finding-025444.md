---
id: 25444
severity: "Low/Info"
---

# proof.length can be used instead ofheight in EcrecoverRatifier.isRatified

## Description



## Proof of Concept

## Impact

Optimization

## Code Snippet

[https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/ratifiers/EcrecoverRatifier.sol#L36-L40](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/ratifiers/EcrecoverRatifier.sol#L36-L40>)

```solidity
(Signature memory sig, uint256 height, bytes32 root, bytes32[] memory proof) =
    abi.decode(ratifierData, (Signature, uint256, bytes32, bytes32[]));
require(HashLib.isLeaf(root, HashLib.hashOffer(offer), proof), InvalidProof());
require(!isRootCanceled[offer.maker][root], RootCanceled());
bytes32 structHash = keccak256(abi.encode(HashLib.offerTreeTypeHash(height), root));
```

## Recommendation

Use `proof.length` instead of height.
