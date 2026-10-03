---
id: 25303
severity: "Low/Info"
---

# CEI pattern is not followed in GovernorTimelock::executeProposals()

## Description



## Proof of Concept

## Vulnerability Detail

As shown below, `GovernorTimelock::executeProposals()` doesn't follow the CEI pattern and allows a malicious executor to reenter in case the proposal passes execution to an executor controlled contract.

## Impact

Depends on the use case, couldn't identify an attack path that resulted in significant damage.

## Code Snippet

[https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R173-R175](<https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R173-R175>)

## Recommendation

Delete the proposal and then make the call.
