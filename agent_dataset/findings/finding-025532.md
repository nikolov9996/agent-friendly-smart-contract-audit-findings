---
id: 25532
severity: "Low/Info"
---

# OstiumLinkUpKeep Config Not Set In initialize()

## Description

The variable [s_config](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumLinkUpKeep.sol#L21>) is not set in the initializer function, which is preferable.

## Proof of Concept

No PoC provided.

## Recommendation

Although setConfig is called right after the deployment of the contract in the deployer script, it will be more efficient to pass the config to the initializer and call setConfig there.
