---
id: 25392
severity: "Crit/High"
---

# deTokenize() is missing access control, anyone can burn other people's nfts

## Description

[deTokenize()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L85>) allows users to burn their nfts with a certain string url. The function is missing access control, such that anyone can burn any nft, POC [here](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/test/test.t.sol#L46>).

## Proof of Concept

No PoC provided.

## Recommendation

Either place the onlyOwner modifier or call _isApprovedOrOwner().
