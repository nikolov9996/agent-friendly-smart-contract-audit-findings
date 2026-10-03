---
id: 25345
severity: "Low/Info"
---

# SyrupBitcoinRouter::requestRedeem() could also check if the asset picked to redeem has liquidity

## Description



## Proof of Concept

## Vulnerability Detail

A user may pick an asset to redeem that has no liquidity, or concurrently with other users it leads to no liquidity, and they would have to remove their shares, or if the withdrawal was processed already in the withdrawal queue, the funds would just be temporarily stuck, since the only option by then is to processRedemptions, but there is no liquidity of that specific asset. At this point, the user can no longer remove their request, which would force Maple to swap assets to fulfill this request, incurring fees/cost.

An example would be if there are 2 assets, 50/50 in allocation, and users decide to withdraw everything in one of the assets, there would be no direct mitigation in place to handle it smoothly.

Note that for this Maple version only wBTC is supported so this issue won't happen.

## Impact

Stuck funds that can be redeem but require Maple to incur costs to swap.

## Code Snippet

[https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R278](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R278>)

## Recommendation

Check if there is liquidity available or prevent this situation from happening in other ways. It may be technically possible to manage this operationally but it doesn't seem easy.
