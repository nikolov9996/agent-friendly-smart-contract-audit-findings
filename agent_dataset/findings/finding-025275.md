---
id: 25275
severity: "Low/Info"
---

# Wrong comment in Standard Governor's execute function

## Description

The following comment is present in [StandardGovernor](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/StandardGovernor.sol>)'s execute function: // Proposals have voteStart=N and voteEnd=N, and can be executed only during epochs N+1 and N+2. This, however, is not the current behaviour of the contract.

As confirmed by the client, approved proposals can only be executed 1 epoch after voteEnd and not 2 epochs as the comment suggests.

## Proof of Concept

No PoC provided.

## Recommendation

Update the comment so it explains the actual behaviour of epoch execution: // Proposals have voteStart=N and voteEnd=N, and can be executed only during N+1 epoch.
