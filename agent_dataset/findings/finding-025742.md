---
id: 25742
severity: "Low/Info"
---

# Any user may enforce the referral code of other new users

## Description

In Endpoint::depositCollateralWithReferral(), the referral is set to

```solidity
DEFAULT_REFERRAL_CODE if it is a remote deposit (sender != address(bytes20(subaccount)). Thus, any user may maliciously set other subaccount
```

referral code to default. It's also possible to do this by submitting a slow mode transaction of type BurnLpAndTransfer.

## Proof of Concept

No PoC provided.

## Recommendation

The specific fix depends on how the referral code is supposed to be handled.
