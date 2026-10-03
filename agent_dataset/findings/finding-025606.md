---
id: 25606
severity: "Crit/High"
---

# Anyone can frontrun a relayer interaction with the same arguments but a much higher/lower relayer fee

## Description

The relayer fee used throughout the codebase is not enforced [anywhere](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/commit/caed73d878d323b218fbef82094264528478c61f>), such that it's possible to frontrun a legit transaction and set a much lower/higher relayer fee, harming the relayer/user.

## Proof of Concept

No PoC provided.

## Recommendation

There are several ways to tackle this issue:

1. Assert that the relayer is the msg.sender.
2. Place a cap on the relayer fee.
3. The relayer gas fee could be part of the message that the user signs.
