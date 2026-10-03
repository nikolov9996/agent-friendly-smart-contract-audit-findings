---
id: 25525
severity: "Medium"
---

# Setting maxFundingFeePerBlock to a lower value than abs(lastFundingRate) will brick getPendingAccFundingFees()

## Description

[getPendingAccFundingFees()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L421>) computes the number of blocks to the limit by subtracting absLastFundingRate to maxFundingFeePerBlock.

[setMaxFundingFeePerBlock()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L306>) allows setting the max to any value below [MAX_FUNDING_FEE](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L27>).

If maxFundingFeePerBlock is set to a value smaller than absLastFundingRate it will underflow, bricking getPendingAccFundingFees() and it can only be fixed by calling [setPairFundingFees()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L171>).

[Here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/poc-maxFundingFeeRate-increase-more-than-current/test/foundry/OstiumPairInfos.t.sol#L1284>) is a POC.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if setMaxFundingFeePerBlock() is called with maxFundingFeePerBlock smaller than absLastFundingRate.
