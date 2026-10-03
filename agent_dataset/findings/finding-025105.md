---
id: 25105
severity: "Crit/High"
---

# Total ETH, WETH and gameETH are not tracked which will lead to insolvency

## Description

Users may upgrade their towers so they receive `gameETH` over time which can later be withdrawn for `ETH`. However, there is no actual tracking in either of the funds, which means that eventually once users stop entering the protocol, there will not be enough ETH to pay everyone for their yield. A [poc](<https://github.com/0x73696d616f/codeup-issues-external/blob/main/test/Codeup.t.sol#L123>) was created showing that after just `16` hours a user receives more `ETH` as yield than their initial deposit when buying `gameETH`.

Thus, initial users that upgrade their towers will just get all yield very quickly from new users, eventually making the protocol insolvent as everyone has yield to claim but nobody wants to deposit.

Another related concern is that users have no option to withdraw their `gameETH`, even if they have for example upgraded their towers to the max level. This essentially means that it does not make sense to ever deposit more than the max cost to upgrade all builders, and users that do so will have just wasted extra funds.

Lastly, the remaining `weth` balance will be impossible to withdraw because the last user that has upgraded their towers to the max builders will withdraw these funds and pay a commision to the pool in `amountForPool`, which will never be recovered.

## Proof of Concept

No PoC provided.

## Recommendation

Users not being able to always get their yield due to the contract not having enough eth is a design choice, as users need to be quick to claim their yield. However, it never makes sense to add more game eth than the amount left needed to fully upgrade their tower, so a check could be added. Additionally, a way to add as liquidity the last weth from commisions should be added.
