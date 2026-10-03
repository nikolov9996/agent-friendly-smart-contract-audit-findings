---
id: 25180
severity: "Crit/High"
---

# In BaseRouter, the beneficiary isn't checked when starting a flashloan action and it replaces the previous beneficiary

## Description



## Proof of Concept

[https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCAttackerChangesBeneficiary.t.sol#L111](<https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCAttackerChangesBeneficiary.t.sol#L111>)

## Recommendation

Add a function to check the beneficiary instead of replacing.
