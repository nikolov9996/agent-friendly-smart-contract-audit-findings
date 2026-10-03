---
id: 25601
severity: "Crit/High"
---

# Checks-effects-interations pattern is not always followed, which can be used to drain all tokens

## Description

[Here](<https://fravoll.github.io/solidity-patterns/checks_effects_interactions.html>) is a writeup about the pattern. Essentially state changes should be handled before interacting with external contracts (for example, when sending ETH via .call(""), to avoid reentrancy.

[Here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L253-L254>) is an example of the code not following it. _postWithdraw() should happen before sending ETH.

So a user can call withdrawETH(), get execution when the ETH is sent, use the same note commitment (still not marked used) to swap on uniswap and double spend. This can be done in a loop to drain all tokens.

## Proof of Concept

No PoC provided.

## Recommendation

Ensure that the codebase follows this pattern.
