---
id: 25134
severity: "Medium"
---

# FairLauncher::participate() should allow specifying a minimum number of shares due to the overfund mechanism

## Description

Users receive discounted shares when they participate in FairLauncher::participate() but the amount raised has exceeded the hard cap set. Thus, users may be frontrunned when participating, receiving less shares than expected.

Maliciously frontrunning on Blast is not possible because the sequencer is centralized and FIFO, but users may still be organically frontrunned.

## Proof of Concept

No PoC provided.

## Recommendation

Attackers can not exploit this but users may still be harmed. A minimum shares amount parameter would be advisable.
