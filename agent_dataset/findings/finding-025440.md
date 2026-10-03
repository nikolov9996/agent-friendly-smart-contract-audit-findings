---
id: 25440
severity: "Low/Info"
---

# BlueBundlesV1::blueBundlesV1RepayAndWithdrawCollateral() may transfer a null leftover

## Description



## Proof of Concept

## Vulnerability Detail

`maxRepayAssets - repayAssets - referralFeeAssets` is 0 whenever `maxRepayAssets` exactly covers the repaid assets plus the fee, which is the natural sizing on an exact assets repay with a null referral fee (`maxRepayAssets == repayAssets`).

## Impact

Tokens reverting on 0 transfer are not supported, so the only impact is consistency throughout the codebase.

## Code Snippet

[BlueBundlesV1.sol#L118-L120](<https://github.com/sherlock-audit/2026-07-morpho-blue-bundles-july-13th-2026/blob/main/morpho-org__bundles/src/blue/BlueBundlesV1.sol#L118-L120>)

```solidity
SafeTransferLib.safeTransfer(
    marketParams.loanToken, msg.sender, maxRepayAssets - repayAssets - referralFeeAssets
);
```

## Recommendation

Skip the transfer when the amount is null, consistent with the rest of the codebase.
