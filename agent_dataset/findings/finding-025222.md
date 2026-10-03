---
id: 25222
severity: "Crit/High"
---

# AaveV3 RewardsController provides rewards in any token, should be handled separately

## Description

The RewardsController from AaveV3 rewards are separate from the yield accrued and can be [several different tokens](<https://docs.aave.com/developers/whats-new/multiple-rewards-and-claim>).

Thus, they should be handled differently.

## Proof of Concept

No PoC provided.

## Recommendation

Add a separate function in AaveV3Strategy that allows us to claim the rewards. Returning the rewards is optional, depending on the option chosen below.

If a strategy has no extra rewards to be claimed, add the function but only return from it to keep compatibility. The ReservePool might end up with tokens other than WAVAX due to the fact that the rewards distributed might be any token. To address this, there are several options:

1. Add a claim rewards function that sends all rewards to the network wallet, so it can swap for wAVAX and increase the network balance.
2. Add a swap function in the ReservePool that swaps all the rewards assets different than WAVAX for WAVAX. If the swap fails, send to the addresses.networkWalletAddress().
