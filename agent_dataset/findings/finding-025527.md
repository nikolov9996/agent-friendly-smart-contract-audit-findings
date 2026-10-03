---
id: 25527
severity: "Low/Info"
---

# Implement Custom Errors Instead of require Statements

## Description

The usage of require statements instead of custom errors is evident in both OstiumLinkUpKeep and particularly in OstiumVault.

## Proof of Concept

No PoC provided.

## Recommendation

It is advisable to opt for custom errors as they offer a more gas-efficient method to explain to users why an operation failed. Additionally, utilizing custom errors is more cost-effective during deployment.
