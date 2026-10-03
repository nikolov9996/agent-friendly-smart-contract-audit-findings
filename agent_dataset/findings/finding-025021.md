---
id: 25021
severity: "Crit/High"
---

# Strike Price Not Validated Against Strike Percent, Leading to Exploitation Risk

## Description



## Proof of Concept

## Impact

The absence of proper checks allows users to input inconsistent `strikePercent` and `strikePrice` values. This leads to reduced option fees while securing gains that should be restricted to lower `strikePercent` values, causing financial losses to the protocol. It also negatively impacts the calculation of [upsideToDeduct](<https://github.com/sherlock-audit/2024-11-autonomint/blob/0d324e04d4c0ca306e1ae4d4c65f0cb9d681751b/Blockchain/Blockchian/contracts/Core_logic/Treasury.sol#L259>), leading to a lower deduction than intended.

## Recommendation

To prevent exploitation, ensure that the `strikePercent` and `strikePrice` are validated against each other at the time of deposit. The following check can be applied:
