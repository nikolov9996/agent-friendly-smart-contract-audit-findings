---
id: 25583
severity: "Crit/High"
---

# totalEarnings is incorrect when withdrawing after ending which will withdraw too many funds leaving the Vault insolvent

## Description



## Proof of Concept

Consider that 2 users have 50% of the variable bearer token each and the protocol starts with 100 ETH and 100 Shares. After some time, the protocol accrues stEth and the holdings become 200 ETH and 100 shares. Before the vault ends, user A withdraws his share of the rewards via `LidoVault::withdraw()`, which is:

```solidity
totalEarnings =  200 * (100 + 0) / 100 - 100 = 100
ethAmountOwed = totalEarnings / 2 = 100 / 2 = 50 // 50% of the bearer tokens, so divides by 2
protocolFee = 50 * 0.05 = 2.5
stakesAmountOwed = 50 / 2 = 25 // each share of stETH is worth 2 ETH, the same ratio as the protocol having 200 ETH and 100 shares.

// RESULT

totalProtocolFee = 2.5
variableToWithdrawnStakingEarningsInShares[userA] = 25
withdrawnStakingEarningsInStakes = 25
ETH = 150
shares = 75
```

Now, assume that the stETH shares double again its value, there are 300 ETH and 75 shares now in the protocol. Consider that the vault ended so the fixed users claimed their 100 ETH, which leaves the protocol with 200 ETH and 50 shares (25 shares were removed to pay the fixed users).

And lastly, userB withdraws his variable rewards by calling `LidoVault::vaultEndedWithdraw()`. The vault has earnings that were not withdrawn, so in the beginning of `LidoVault::vaultEndedWithdraw()` it requests the entire balance of the contract and registers the following:

```solidity
vaultEndingStakesAmount = 50
vaultEndingETHBalance = 200
```

Then, `LidoVault::finalizeVaultEndedWithdrawals()` is called, which claims the withdrawals, getting 200 ETH and setting the following variables:

```solidity
amountWithdrawn = 200 ETH
fixedETHDeposit = 0 // was withdrawn by the fixed users already
vaultEndedStakingEarnings = 200 - 200 * 0.05 = 200 - 10 = 190
```

And finally, it calls again `LidoVault::vaultEndedWithdraw()` at the end, which leads to the following `totalEarnings` calculations:

```solidity
totalEarnings = 200 * 25 / 50 - 2.5 + 190 = 287.5
ethAmountOwed = totalEarnings / 2 = 287.5 / 2 = 143.75
```

At this point, there is 190 ETH in the contract, and userA has withdrawn 25 shares, but userB has not withdrawn any shares. In the first time the stETH shares price doubled, they both had the same shares, so they should get the same amount. However, by the end, the stETH shares price doubled again, but one user had already withdrawn. Intuitively, this means that userB, who has not withdrawn, should get 75% of the final earnings while user A should get 25%, but this is not what happens. `variableToWithdrawnStakingEarningsInShares[userB] == 0`, so userB will withdraw `143.75 / 190 ~= 0.757`.

To fix this, if we take the `totalProtocolFee` in shares instead of flat, when userA withdrew the first time, it withdraw 2.5 in fees, which at the time was 1.25 shares (it doubled). This yields:

```solidity
totalEarnings = 200 * 25 / 50 - 1.25 * 200 / 50 + 190 = 285
ethAmountOwed = totalEarnings / 2 = 285 / 2 = 142.5
```

And lastly, `142.5 / 190 == 0.75`, which is the correct amount.

Additionally, if we calculate userA's amount, it will be wrong too and shows us how it does not add up. We just need to subtract the shares of userA worth in ETH to the `totalEarnings / 2` to get his part:

```solidity
ethAmountOwed = 143.75 - 25 * 200 / 50 = 43.75
```

So summing up, they get `143.5 + 43.75 == 187.25`, which is less than 190 and some ETH is stuck. The amount is lower than 190, but it should be higher, the issue is that there is another bug, which is, the component that userA has already withdrawn should be discounted by the shares paid in fees (1.25). If we do this, it becomes

```solidity
ethAmountOwed = 143.75 - (25 - 1.25) * 200 / 50 = 48.75
```

Now, summing both users' withdrawals, `143.75 + 48.75 == 192.5`, which is bigger than 190 and they will withdraw too much.

## Recommendation

`totalProtocolFee` must be tracked as shares in `LidoVault.sol:533`.

```solidity
totalProtocolFee += lido.getSharesByPooledEth(protocolFee);
```
