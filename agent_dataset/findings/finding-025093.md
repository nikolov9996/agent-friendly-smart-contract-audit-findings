---
id: 25093
severity: "Medium"
---

# Compounding shares will overtime get less rewards than non compounding shares

## Description

keepPortion and sellPortion are based on the total number of shares of each type. However, compoundShareRate is expected to increase due to accumulating rewards.

This means that, for compounding shares, the same liquidity minted compared to non compounding shares will lead to less shares, when depositing.

Thus, over time, assuming equal deposits of compounding and non compounding shares, the total supply of non compounding shares is expected to grow more than compounding shares.

## Proof of Concept

No PoC provided.

## Recommendation

keepPortion and sellPortion should be calculated based on the total liquidity of each share type, not the total supply, as liquidity is effectively what is generating rewards.
