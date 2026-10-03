---
id: 25324
severity: "Low/Info"
---

# In MapleGlobals, there is no check in the dataHash argument when unscheduling a call.

## Description

In MapleGlobals.sol, in unscheduleCall(), the CallUnscheduled event is emitting dataHash (the hash of the callData_) which is never checked, and could be different than the one it is unscheduling.

## Proof of Concept

No PoC provided.

## Recommendation

- emit the dataHash in storage (in the struct) and don't take the callData_ as an argument to the function unscheduleCall() or
- verify that the dataHash is valid before emitting by comparing it to the one in storage
