---
id: 25511
severity: "Medium"
---

# USDC Blacklisting Prevents Trader Liquidation

## Description

USDC incorporates a blacklist functionality that reverts any attempt to transfer funds to a blacklisted address, even if the transfer amount is 0.

Consequently, during a liquidation, the transfer on [L495](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTradingCallbacks.sol#L495>) within OstiumTradingCallbacks will revert, preventing the liquidation from proceeding and resulting in bad debt for the protocol.

Likewise, other functions such as OstiumTrading::cancelOpenLimitOrder(), OstiumTrading::openTradeMarketTimeout(), and OstiumTradingCallbacks::openTradeMarketCallback() will also revert upon transferring the collateral back to the trader.

A Proof of Concept is available [here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/test/foundry/OstiumTradingCallback.t.sol#L1642>).

## Proof of Concept

No PoC provided.

## Recommendation

To address this issue, we suggest one or more of the following solutions:

- Blacklist Check During Borrowing: Implement a check for USDC blacklisting during the loan initiation process to prevent blacklisted users from opening a loan position until their status is resolved. However, this is not a complete solution, as a user's blacklist status may change between the initiation of a trade and its liquidation.
- Alter Liquidation Flow: Eliminate the transfer of remaining USDC tokens to the liquidated user during the liquidation process. Instead, adopt a pull-over-push method, enabling users to withdraw their remaining USDC tokens independently after the liquidation process is complete.
