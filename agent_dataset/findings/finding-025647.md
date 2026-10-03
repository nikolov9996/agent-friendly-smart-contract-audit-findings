---
id: 25647
severity: "Medium"
---

# Program start failure due to incorrect buffer calculation

## Description



## Proof of Concept

None.

## Impact

DoSed `FluidEPProgramManager::startFunding()`. Not only it is time sensitive, but also it won't allow the admin to start flows with all possible values, which is key functionality.

## Recommendation

Calculate the buffer individually for each flow rate.
