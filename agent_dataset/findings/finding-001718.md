---
id: 1718
severity: "High"
---

# totalEarnings is incorrect when withdrawing

## Description

totalEarnings in LidoVault::vaultEndedWithdraw() is calculated as:
```solidity
uint256 totalEarnings = vaultEndingETHBalance.mulDiv(
    withdrawnStakingEarningsInStakes, vaultEndingStakesAmount
) - totalProtocolFee + vaultEndedStakingEarnings;
```
The withdrawn shares are scaled to get the total earnings, along with vaultEndedStakingEarnings, which was acquired by getting the liquidity from the remaining shares when LidoVault::finalizeVaultEndedWithdrawals() was called.
However, totalProtocolFee is not scaled, which means that as the steth eth/shares ratio increases, the protocol fee increases with it, otherwise it will overestimate the totalEarnings, as can be confirmed in the calculations in the POC.
In LidoVault.sol:775, protocolFee is not scaled to the current steth eth/shares. It should be in shares and multiplied by the current exchange rate. In LidoVault.sol:533, protocolFee should be tracked as shares.
Internal pre-conditions
None.
External pre-conditions
None.
Attack Path
1. Users withdraw via LidoVault::vaultEndedWithdraw() and withdraw more than they should due to the total earnings. Next users will not have enough funds to make their withdrawals, taking a loss for the profit of the earlier users.
The protocol becomes insolvent.

## Proof of Concept

Consider that 2 users have 50% of the variable bearer token each and the protocol starts with 100 ETH and 100 Shares. After some time, the protocol accrues stEth and the holdings become 200 ETH and 100 shares. Before the vault ends, user A withdraws his share of the rewards via LidoVault::withdraw(), which is:
totalEarnings = 200 * (100 + 0) / 100 - 100 = 100
ethAmountOwed = totalEarnings / 2 = 100 / 2 = 50 // 50% of the bearer tokens, so divides by 2
protocolFee = 50 * 0.05 = 2.5
stakesAmountOwed = 50 / 2 = 25 // each share of stETH is worth 2 ETH, the same ratio as the protocol having 200 ETH and 100 shares.
// RESULT
totalProtocolFee = 2.5
variableToWithdrawnStakingEarningsInShares[userA] = 25
withdrawnStakingEarningsInStakes = 25
ETH = 150
shares = 75
Now, assume that the stETH shares double again its value, there are 300 ETH and 50 shares And lastly, userB withdraws his variable rewards by calling LidoVault::vaultEndedWithdraw(). The vault has earnings that were not withdrawn, so in the beginning of LidoVault::vaultEndedWithdraw() it requests the entire balance of the contract and registers the following:
vaultEndingStakesAmount = 50
vaultEndingETHBalance = 200
Then, LidoVault::finalizeVaultEndedWithdrawals() is called, which claims the withdrawals, getting 200 ETH and setting the following variables:
amountWithdrawn = 200 ETH
vaultEndedStakingEarnings = 200 - 200 * 0.05 = 200 - 10 = 190
And finally, it calls again LidoVault::vaultEndedWithdraw() at the end, which leads to the following totalEarnings calculations:
totalEarnings = 200 * 25 / 50 - 2.5 + 190 = 287.5
ethAmountOwed = totalEarnings / 2 = 287.5 / 2 = 143.75
At this point, there is 190 ETH in the contract, and userA has withdrawn 25 shares, but userB has not withdrawn any shares. In the first time the stETH shares price doubled, they both had the same shares, so they should get the same amount.
However, by the end, the stETH shares price doubled again, but one user had already withdrawn. Intuitively, this means that userB, who has not withdrawn, should get more ETH since the ETH per share increased and he did not withdraw.
To fix this, if we take the totalProtocolFee in shares instead of flat, when userA withdrew the first time, it withdraw 2.5 in fees, which at the time was 1.25 shares (it doubled). This yields:
totalEarnings = 200 * 25 / 50 - 1.25 * 200 / 50 + 190 = 285
ethAmountOwed = totalEarnings / 2 = 285 / 2 = 142.5
And lastly, 142.5 / 190 == 0.75, which is the correct amount.
Additionally, if we calculate userA's amount, it will be wrong too and shows us how it does not add up. We just need to subtract the shares of userA worth in ETH to the totalEarnings / 2 to get his part:
ethAmountOwed = 143.75 - 25 * 200 / 50 = 43.75
So summing up, they get 143.75 + 43.75 == 187.5, which is less than 190 and some ETH is stuck. The amount is lower than 190, but it should be higher, the issue is that there is another bug, which is, the component that userA has already withdrawn should be discounted by the shares paid in fees (1.25). If we do this, it becomes ethAmountOwed = 143.75 - (25 - 1.25) * 200 / 50 = 48.75
Now, summing both users' withdrawals, 143.75 + 48.75 == 192.5, which is bigger than 190 and they will withdraw too much.

## Recommendation

totalProtocolFee must be tracked as shares in LidoVault.sol:533.
```solidity
totalProtocolFee += lido.getSharesByPooledEth(protocolFee);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error in the LidoVault withdrawal logic where the protocol fee is stored and applied as a raw ETH amount instead of being scaled to the current stETH‑to‑ETH share ratio. The contract calculates totalEarnings by scaling the withdrawn staking earnings and adding the earnings from remaining shares, but it subtracts totalProtocolFee without converting that fee into shares. Because the share price can change between withdrawals, the unscaled fee grows proportionally with the share price, causing the totalEarnings figure to be inflated for early withdrawers and deflated for later ones. An attacker can exploit this by withdrawing early, receiving more ETH than entitled, while subsequent users receive less than their proportional share, potentially leaving the vault insolvent. The impact is that users may receive an incorrect refund – they expect to get their share of the vault’s earnings but may receive too much or too little, balances can become unexpectedly low or zero, and the protocol’s total funds can be depleted. The bug manifests whenever the vault is in the “ended” state and multiple users perform withdrawals across periods where the stETH/ETH exchange rate changes. All participants who hold vault shares are affected, as are the protocol’s fee revenue and overall solvency. The issue was discovered during a manual audit that compared the mathematical model of fee scaling with the actual implementation and produced a proof‑of‑concept showing over‑payment. It is hard to notice because the numbers look plausible in a single withdrawal and only diverge after the share price changes, making the discrepancy subtle. The correct fix is to track totalProtocolFee in shares rather than ETH, converting the fee using the current exchange rate whenever it is applied, and to update the fee accounting at the point where shares are minted or burned. This aligns the fee with the same scaling logic used for earnings, restores proper accounting, and prevents users from receiving an incorrect amount of ETH during vault withdrawals.
