---
id: 25426
severity: "Low/Info"
---

# Cap::_checkRemoteStateAndAdvance() may be optimized by returning early as soon as a different epoch is found in a remote domain

## Description

Cap::_checkRemoteStateAndAdvance() advances the next epoch if all domains are equal to the minimum domain found. Thus, if any of the domains is not equal to the minimum, it will return anyway.

## Proof of Concept

No PoC provided.

## Recommendation

Given that it returns if any of epochs of the domains is different, there is no need to search for the minimum. It's enough picking the domain of index 0 and returning if any of the other domains is not the same.

It later only advances the epoch if the epoch of the domains is bigger than the local, so if they all match the current local domain, it will not advance anyway.
