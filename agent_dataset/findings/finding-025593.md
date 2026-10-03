---
id: 25593
severity: "Crit/High"
---

# Curve multi exchange does not validate assetIn and assetOut against route

## Description

CurveMultiExchangeAssetManager::curveMultiExchange() receives arguments assetIn, assetOut and route. Route is defined as Array of [initial token, pool or zap, token, pool or zap, token, ...] . The CurveRouter::exchange() assumes the assetIn is route[0] and assetOut is the last non null address in route that represents a token out.

This means one of the indexes 2, 4, 6, 8, 10, depending on which one precedes a null. Thus, knowing that this validation is missing, it's possible to specify an assetOut of a valuable token, but place in the route a fake coin.

By doing so, and introducing a malicious pool to swap, the exchange contract will receive a large amount of fake coins, returning this amount, but the CurveMultiExchangeAssetManager will think it is assetOut instead.

The transaction could still revert when transferring assetOut, as the exchange did not actually send the real assetOut, but it won't due to issue #12.

However, the deposit note is still created and the funds can be stolen. [Here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/fuzzing/test/foundry/CurveMultiExchangeAssetManager.t.sol#L91>) is a poc.

## Proof of Concept

No PoC provided.

## Recommendation

Validate assetIn and assetOut against the route. assetIn should be route[0] and assetOut should match the last non null token index, as described above.
