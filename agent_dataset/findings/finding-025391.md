---
id: 25391
severity: "Crit/High"
---

# NFTs can be stolen by calling send() and receiving the nfts in another chain

## Description

[send()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L98>) does not check the owner of the to be sent nfts, which allows anyone to send nfts to itself on behalf of someone else. See the POC [here](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/test/test.t.sol#L68>).

## Proof of Concept

No PoC provided.

## Recommendation

Add _isApprovedOrOwner() on the nfts to be sent in send().
