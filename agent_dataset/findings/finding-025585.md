---
id: 25585
severity: "Medium"
---

# Withdrawing after a slash event before the vault has ended will decrease fixedSidestETHOnStartCapacity by less than it should, so following users will withdraw more their initial deposit

## Description



## Proof of Concept

Assume that there 100 ETH and 100 shares. A slashing event occurs and drops the ETH to 90 and shares remain 100. There are 2 fixed depositors, with 50% of the deposits each. User A withdraws, and should take `100 ETH  50 / 100 == 50 ETH`*, but takes `90 ETH `*` 50 / 100 == 45 ETH` instead due to the loss. `fixedSidestETHOnStartCapacity` is decreased by `45 ETH`, the withdrawn amount, so it becomes `55 ETH`. Now, when LIDO recovers from the slashing, the contract will hold more steth than `fixedSidestETHOnStartCapacity`, more specifically the remaining 45 ETH in the contract that were not withdrawn yet are worth 50 ETH now. So user B gets `fixedSidestETHOnStartCapacity * 50 / 50 == 55`.

As the fixed deposit user initially deposited 50, but claimed 55 now, it is getting much more than it should at the expense of the variable users who will take the loss.

## Recommendation

The `fixedSidestETHOnStartCapacity` should be always reduced by `fixedETHDeposits.mulDiv(fixedBearerToken[msg.sender], fixedLidoSharesTotalSupply());`, such that users get their equivalent ETH from their initial deposit back and the variable users don't take losses.
