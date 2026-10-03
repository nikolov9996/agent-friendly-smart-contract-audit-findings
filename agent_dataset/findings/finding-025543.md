---
id: 25543
severity: "Low/Info"
---

# OstiumPriceUpKeep Verifies Reports Using Native Token Instead of LINK

## Description

The [Chainlink documentation](<https://docs.chain.link/data-streams#billing>) states that verifying data streams via native blockchain gas tokens and their ERC20-wrapped versions incurs a surcharge when compared to LINK payments.

However, the payment for verification on [L126](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumPriceUpKeep.sol#L126>) is conducted using the native token, suggesting that it would be more cost-effective for the protocol to use LINK for payments.

## Proof of Concept

No PoC provided.

## Recommendation

It is advised to consult the specific section within the [documentation](<https://docs.chain.link/data-streams/getting-started#examine-the-code>) that details the implementation of payments using LINK and follow those guidelines.
