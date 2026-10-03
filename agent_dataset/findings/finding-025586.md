---
id: 25586
severity: "Medium"
---

# LidoVault::vaultEndedWithdraw doesn't take into consideration income withdrawals before slashing, blocking variable users from withdrwing their income

## Description



## Proof of Concept

Add the following test in `lido-fiv/test/1.LidoVault.test.ts`:

```typescript
it("BUG - DOS, can't withdraw after Slashing", async () => {
  const { lidoVault, addr1, addr2, addr3 } = await loadFixture(deployLidoVaultFixture)
  const { lidoMock } = await setupMockLidoContracts(lidoVault)

  // Users deposit FIXED and VARIABLE
  await lidoVault.connect(addr1).deposit(SIDE.FIXED, { value: parseEther('1000') })
  await lidoVault.connect(addr2).deposit(SIDE.VARIABLE, { value: parseEther('15') })
  await lidoVault.connect(addr3).deposit(SIDE.VARIABLE, { value: parseEther('15') })

  // Vault has started
  expect(await lidoVault.isStarted()).to.equal(true)

  // User 1 claims FIXED premium
  await lidoVault.connect(addr1).claimFixedPremium()

  // Half time passes
  const { duration, endTime } = await getTimeState(lidoVault)
  await time.increaseTo(endTime - duration / BigInt(2))

  // Lido rebasing, vault earns 100 ETH
  await lidoMock.addStakingEarningsForTargetETH(
    parseEther('1100'),
    await lidoVault.getAddress()
  )

  // User 2 withdraws their income (part of the above rebasing)
  await lidoVault.connect(addr2).withdraw(SIDE.VARIABLE)

  // Withdrawal was sent to Lido
  expect(
    (await lidoVault.getVariableToVaultOngoingWithdrawalRequestIds(addr2.address)).length
  ).to.equal(1)
  // `withdrawnStakingEarningsInStakes` is now > 0
  expect(await lidoVault.withdrawnStakingEarningsInStakes()).to.be.greaterThan(0)

  // End time passes
  await time.increaseTo(endTime + BIG_INT_ONE)

  // Vault is ended
  expect(await lidoVault.isEnded()).to.equal(true)

  // Lido slashes the vault
  await lidoMock.subtractStakingEarnings(parseEther('50'))

  // User 1 withdraws their FIXED deposit
  await lidoVault.connect(addr1).withdraw(SIDE.FIXED)
  await lidoVault.connect(addr1).finalizeVaultEndedWithdrawals(SIDE.FIXED)

  // User 3 can't withdraw his income
  await expect(
    lidoVault.connect(addr3).finalizeVaultEndedWithdrawals(SIDE.VARIABLE)
  ).to.be.revertedWith('ETF')
})
```

## Recommendation

In `LidoVault::vaultEndedWithdraw`, when calculating the `totalEarnings` when a variable user is withdrawing, consider the income that was withdrawn before Lido slashing happens. Maybe have something like the following?

```solidity
totalEarnings = Math.min(totalEarnings, vaultEndingETHBalance);
```
