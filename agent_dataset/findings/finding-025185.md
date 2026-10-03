---
id: 25185
severity: "Medium"
---

# Users can claim tokens in ConnextRouter by calling xReceive(...) directly

## Description

The ConnextRouter allows anyone to call xReceive(...) and the amount of assets the user provided is the [balance of the contract](<https://github.com/Fujicracy/fuji-v2/blob/v0.1.0/packages/protocol/src/routers/ConnextRouter.sol#L148>).

Thus, users can use this functionality to sweep any existing funds into their wallets. In fact, this should also happen when a xReceive(...) call fails at this.xBundleConnext(...), and the balance, including the existing tokens, get attributed to the user.

It should not be a likely event given that there are checks to ensure that the ConnextRouter does not end up with funds after xBundle(...) calls. Still, given that the BaseRouter has a sweepTokens(...) function, this might lead to a false sense of security.

## Proof of Concept

No PoC provided.

## Recommendation

Only let a permissioned address call xReceive(...) (should be the xConnect address). Additionally, instead of sending the balance in the ConnextRouter if this.xBundleConnext(actions, args, beforeSlipped) fails, send the amount.
