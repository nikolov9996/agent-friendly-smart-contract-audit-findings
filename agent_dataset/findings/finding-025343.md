---
id: 25343
severity: "Low/Info"
---

# SortedLinkedList::getAllValues() could add a paginated function to prevent DoS

## Description



## Proof of Concept

## Vulnerability Detail

There are onchain gas limits and rpc providers may timeout even if there isn't an offchain limit.

## Code Snippet

[https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/26/files#diff-039b765c6733ead864f7a36bdbf1e880064e5d25e276a3b3cde1cb4935dc7e12R101](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/26/files#diff-039b765c6733ead864f7a36bdbf1e880064e5d25e276a3b3cde1cb4935dc7e12R101>)

## Recommendation

Usually a separate paginated function is added as an alternative.
