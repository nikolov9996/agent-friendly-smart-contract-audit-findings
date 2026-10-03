---
id: 25002
severity: "Low/Info"
---

# uniTransfer() limits the gas limit to 5k in outdated 1inch solidity-utils lib

## Description



## Proof of Concept

## Vulnerability Detail

See the version used in the current commit of the protocol [here](<https://github.com/1inch/solidity-utils/blob/26969f67e5ee32ad70d07ed1c3a8066ed2ede5e1/contracts/libraries/UniERC20.sol#L69>).

The solidity-utils lib has been updated in 6.4.0 and now forwards all gas, which means that the only fix needed is bumping this version in the package.json file.

## Impact

Sweeping could fail due to this limitation. Another owner would have to be used, that most likely can not be a multisig so it could be a problem.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/FeeTaker.sol#L97-L99](<https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/FeeTaker.sol#L97-L99>)

## Recommendation

Bump the solidity utils version to the latest.
