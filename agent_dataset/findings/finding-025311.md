---
id: 25311
severity: "Low/Info"
---

# GovernorTimelock::_call() assembly revert block doesn't have the memory safe attribute

## Description



## Proof of Concept

## Vulnerability Detail

Essentially certain optimizations are disabled when memory safe is not set in the assembly blocks, which is not recommended.

## Impact

Undefined but it's better to follow the recommendations.

## Code Snippet

[https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R225](<https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R225>)

## Recommendation

Add memory safe as per the OZ implementation.
