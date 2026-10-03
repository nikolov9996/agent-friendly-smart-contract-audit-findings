---
id: 25250
severity: "Crit/High"
---

# _rebalanceWithdraw() mechanism in glAVAX allows arbitrage opportunities by changing the shares/AVAX ratio

## Description

The balance available for withdrawals is tracked in address(this).balance. The implementation itself is correct and users will have enough liquidity to withdraw given enough balance is accumulated.

However, withdrawing should be done atomically; AVAX should not be withdrawn when withdraws are rebalanced and the shares burned when the requests are fulfilled. Essentially, whenever possible changing the ratio shares/wAVAX ratio should be avoided to prevent MEV opportunities.

## Proof of Concept

No PoC provided.

## Recommendation

Since there are considerable changes involved, a [POC](<https://github.com/threesigmaxyz/glacier-contracts-foundry/blob/audit-12-07-2023/contracts/protocol/GlacialAVAX/glAVAXWithdrawPOC.sol>) was pushed. In short, instead of withdrawing AVAX and keeping it in the glAVAX contract, a reserved wAVAX amount is tracked, always keeping the shares/wAVAX ratio intact.
