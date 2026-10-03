---
id: 25595
severity: "Crit/High"
---

# Curve multi exchange can be used to withdraw assets without paying fees

## Description

CurveMultiExchangeAssetManager::exchange() allows sending any route, which is of type Array of [initial token, pool or zap, token, pool or zap, token, ...]. The pool or zap chosen indexes are not validated, which means any contract can be specified.

Thus, users can create a contract with the same interface as pool or zap and receive the amountIn there. Then, only send back a very small amount of token out to bypass the fee manager check in calculateFee() of the amount being bigger than serviceCharge + relayerRefund. The service fees will be very small and the user will get the funds right away.

The [poc](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/commit/15579b3292a2ba64e6366359eab22a5774c44edd#diff-2ca8b97729682cb38022f50764c9ff79acfcb1b4520988d573457c6b91cb7d3dR14>) for issue #13 contains an example of a malicious swap contract.

## Proof of Concept

No PoC provided.

## Recommendation

Apply the fees when releasing assetIn instead, this way it can not be gamed.
