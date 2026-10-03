---
id: 25520
severity: "Low/Info"
---

# Wrong decoding of verifierResponse in OstiumPriceUpKeep::performUpkeep()

## Description

[OstiumPriceUpKeep::performUpkeep()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L103>) decodes the verifierResponse setting an expiresAt as [uint192](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L138-L145>), when it is in fact a uint32 in both [Basic](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/test/foundry/OstiumPriceUpKeep.t.sol#L30>) and [Premium](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/test/foundry/OstiumPriceUpKeep.t.sol#L40>) reports.

This has no impact as the variables are encoded as uint256 with abi.encode(), but should be addressed. Note: [here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L113-L119>) too.

## Proof of Concept

No PoC provided.

## Recommendation

Instead of decoding each element separately, decode to a BasicReport or PremiumReport struct.
