---
id: 25584
severity: "Medium"
---

# Attacker will DoS LidoVault up to 36 days which will ruin expected apr for all parties involved

## Description



## Proof of Concept

Look at the function `LidoVault::vaultEndedWithdraw()` for confirmation.

## Impact

36 days DoS, which means the protocol can not get the expected interest rate calculated.

## Recommendation

Firstly, an attacker should not be able to transfer 100 wei of steth and initiate a request because of this. The threshold should be computed based on an estimated earnings left to withdraw for variable depositors and fixed depositors that have not claimed, not just 100.

Secondly, it would be best if there was an alternative way to withdraw in case requests are taking too much.
