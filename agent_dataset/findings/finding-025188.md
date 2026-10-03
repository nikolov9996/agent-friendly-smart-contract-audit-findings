---
id: 25188
severity: "Crit/High"
---

# Attackers can claim deposits to vaults if users specify the router as receiver and don't withdraw shares after

## Description



## Proof of Concept

[https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCAttackerStealsUser.t.sol#L40](<https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCAttackerStealsUser.t.sol#L40>)

## Recommendation

Add to the tokensToCheck array the address of the vault itself (its shares).
