---
id: 25251
severity: "Medium"
---

# Withdraw snapshot logic can be tricked allowing users to withdraw right away

## Description

The current withdraw snapshot implementation allows users to withdraw a certain amount after other users withdraw this amount. It is a fair system such that users that want to withdraw a bigger quantity have to wait more time.

However, the system can be tricked by splitting the withdrawal amount into smaller parts. For example, someone who wants to withdraw 50000 AVAX would have to wait for other people to withdraw 50000 AVAX first before they can withdraw.

However, if this person placed 1000 withdrawal requests of 50 AVAX each, they could withdraw their 50000 AVAX just after 50 AVAX is withdrawn from other users, not the full 50000.

## Proof of Concept

No PoC provided.

## Recommendation

Withdraw requests are placed whenever there is not enough liquidity to enable user withdrawals. Thus, users have to wait for deposits or fulfillWithdrawal() calls from the network. As the current implementation can be tricked, it's safer to fallback to a slightly less elegant solution.

Similarly to [Benqi Finance](<https://github.com/Benqi-fi/BENQI-Smart-Contracts/blob/master/sAVAX/StakedAvax.sol#L610>), use timestamps to allow users to claim their withdrawal requests.

There should be a cooldown period that they have to wait to be able to claim their withdrawal request and a redeem period which after it, the reserved wAVAX can be placed again to the network.
