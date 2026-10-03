---
id: 25628
severity: "Low/Info"
---

# Variables are initialized to 0 by default

## Description

Some variables such as [these](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/889667f80217ebe2788cba40bebda18a1ef13ecb/contracts/defi/curve/CurveMPAddLiquidityAssetManager.sol#L197-L198>) are initialized to 0, which is not necessary.

## Proof of Concept

No PoC provided.

## Recommendation

Consider not initializing the variables as it is not required.
