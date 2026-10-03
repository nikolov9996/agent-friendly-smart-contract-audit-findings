---
id: 25405
severity: "Low/Info"
---

# The current epoch will never advance if there are no other domains

## Description

In Cap::_processDone(), it returns if no domains are set, if (domains.length == 0) return;. This means it will be impossible to advance epoch if there are no domains set, which may be fine as the cap can be increased either way.

## Proof of Concept

No PoC provided.

## Recommendation

Consider adding a comment with the intended behaviour or modify it if required.
