---
id: 25453
severity: "Medium"
---

# BoldToken initialization can be frontrun to silently mint/approve bold to an attacker

## Description



## Proof of Concept

## Vulnerability Detail

`BoldToken::initialize()` is called seperately after the constructor, which means that if sent in different txs (depending on deployment scripts, it may be possible to mitigate if sent via a multicall), an attacker can frontrun the deployment, initialize the `BoldToken` to a malicious implementation, mint/approve `Bold` to their address and then set the implementation to `address(0)` so the script does not revert and the `BoldToken::initialize()` call succeeds.

## Impact

Attackers mints/gets `Bold` for free.

## Code Snippet

[https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BoldToken.sol#L59-L72](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BoldToken.sol#L59-L72>) [https://github.com/superfluid-finance/protocol-monorepo/blob/1edc4ed3ddafa87d42c1155e870532e2a5a80470/packages/ethereum-contracts/contracts/upgradability/UUPSProxy.sol#L25-L29](<https://github.com/superfluid-finance/protocol-monorepo/blob/1edc4ed3ddafa87d42c1155e870532e2a5a80470/packages/ethereum-contracts/contracts/upgradability/UUPSProxy.sol#L25-L29>)

## Recommendation

Use a multicall to deploy or move the `BoldToken::initialize()` logic to the constructor.
