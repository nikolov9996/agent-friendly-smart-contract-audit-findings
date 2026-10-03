---
id: 25515
severity: "Medium"
---

# Casting from int256 to uint256 won't revert if the number is negative, possibly leading to issues

## Description

Some instances, namely in [OstiumPairInfos::getPendingAccFundingFees()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L447-L473>), cast int256 to uint256.

## Proof of Concept

No PoC provided.

## Recommendation

Avoid casting directly and use a wrapper library instead such as SafeCastUpgradeable.
