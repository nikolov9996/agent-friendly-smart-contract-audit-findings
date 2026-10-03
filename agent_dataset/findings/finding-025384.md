---
id: 25384
severity: "Medium"
---

# mintGenesis() mints with a push pattern using _mint() which may lead to lost tokens

## Description

[_mint()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L60>) in [mintGenesis()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L67>) may send tokens to an address that can't deal with ERC721. _safeMint() would be recommended; however, it would introduce additional issues, namely reentrancy and possible malicious reverts.

## Proof of Concept

No PoC provided.

## Recommendation

Use a merkle tree to allow users to claim their genesis NFTs. This way, each user is responsible for claiming their NFT correctly. Additionally, it would be much cheaper for the owner of the MetaZeroVortex contract and the isGenesis mapping could be verified against the merkle tree, saving up to 1000 storage writes.
