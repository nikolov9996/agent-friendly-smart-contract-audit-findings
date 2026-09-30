---
id: 22288
severity: "High"
---

# Users may encounter losses on assets deposited through `StrategySupplyERC4626`

## Description

```solidity
The `_deploy()`, `_undeploy()`, and `_getBalance()` functions of `StrategySupplyERC4626` currently return the amount of shares instead of the amount of the underlying asset. This mistake leads to incorrect calculations of user assets within any BakerFi Vault that utilizes `StrategySupplyERC4626`.
```

## Proof of Concept

When a user deposits a certain amount of asset (`deployedAmount`) into a BakerFi vault, it is deployed into the vault’s underlying strategies. In return, the user receives a corresponding number of `shares`:
```solidity
function _depositInternal(uint256 assets, address receiver) private returns (uint256 shares) {
    if (receiver == address(0)) revert InvalidReceiver();
    // Fetch price options from settings
    // Get the total assets and total supply
    Rebase memory total = Rebase(totalAssets(), totalSupply());

    // Check if the Rebase is uninitialized or both base and elastic are positive
    if (!((total.elastic == 0 && total.base == 0) || (total.base > 0 && total.elastic > 0))) {
        revert InvalidAssetsState();
    }

    // Check if deposit exceeds the maximum allowed per wallet
    uint256 maxDepositLocal = getMaxDeposit();
    if (maxDepositLocal > 0) {
        uint256 depositInAssets = (balanceOf(msg.sender) * _ONE) / tokenPerAsset();
        uint256 newBalance = assets + depositInAssets;
        if (newBalance > maxDepositLocal) revert MaxDepositReached();
    }

    uint256 deployedAmount = _deploy(assets);

    // Calculate shares to mint
    shares = total.toBase(deployedAmount, false);

    // Prevent inflation attack for the first deposit
    if (total.base == 0 && shares < _MINIMUM_SHARE_BALANCE) {
        revert InvalidShareBalance();
    }

    // Mint shares to the receiver
    _mint(receiver, shares);

    // Emit deposit event
    emit Deposit(msg.sender, receiver, assets, shares);
}
```
To withdraw their deployed assets from a BakerFi vault, users must burn a corresponding number of shares to receive a certain amount of assets:
```solidity
function _redeemInternal(
    uint256 shares,
    address receiver,
    address holder,
    bool shouldRedeemETH
) private returns (uint256 retAmount) {
    if (shares == 0) revert InvalidAmount();
    if (receiver == address(0)) revert InvalidReceiver();
    if (balanceOf(holder) < shares) revert NotEnoughBalanceToWithdraw();

    // Transfer shares to the contract if sender is not the holder
    if (msg.sender != holder) {
        if (allowance(holder, msg.sender) < shares) revert NoAllowance();
        transferFrom(holder, msg.sender, shares);
    }

    // Calculate the amount to withdraw based on shares
    uint256 withdrawAmount = (shares * totalAssets()) / totalSupply();
    if (withdrawAmount == 0) revert NoAssetsToWithdraw();

    uint256 amount = _undeploy(withdrawAmount);
    uint256 fee = 0;
    uint256 remainingShares = totalSupply() - shares;

    // Ensure a minimum number of shares are maintained to prevent ratio distortion
    if (remainingShares < _MINIMUM_SHARE_BALANCE && remainingShares != 0) {
        revert InvalidShareBalance();
    }

    _burn(msg.sender, shares);

    // Calculate and handle withdrawal fees
    if (getWithdrawalFee() != 0 && getFeeReceiver() != address(0)) {
        fee = amount.mulDivUp(getWithdrawalFee(), PERCENTAGE_PRECISION);

        if (shouldRedeemETH && _asset() == wETHA()) {
            unwrapETH(amount);
            payable(receiver).sendValue(amount - fee);
            payable(getFeeReceiver()).sendValue(fee);
        } else {
            IERC20Upgradeable(_asset()).transfer(receiver, amount - fee);
            IERC20Upgradeable(_asset()).transfer(getFeeReceiver(), fee);
        }
    } else {
        if (shouldRedeemETH) {
            unwrapETH(amount);
            payable(receiver).sendValue(amount);
        } else {
            IERC20Upgradeable(_asset()).transfer(receiver, amount);
        }
    }

    emit Withdraw(msg.sender, receiver, holder, amount - fee, shares);
    retAmount = amount - fee;
}
```
As we can see, the return values of `_deploy()` and `_undeploy()` should represent the amount of asset. In addition, `_totalAssets()` should also return the amount of asset. The implementation of the above functions within the `Vault` contract is as follows:
```solidity
function _deploy(uint256 assets) internal virtual override returns (uint256 deployedAmount) {
    // Approve the strategy to spend assets
    IERC20Upgradeable(_strategyAsset).safeApprove(address(_strategy), assets);
    // Deploy assets via the strategy
    deployedAmount = _strategy.deploy(assets); // Calls the deploy function of the strategy
}

function _undeploy(uint256 assets) internal virtual override returns (uint256 retAmount) {
    retAmount = _strategy.undeploy(assets); // Calls the undeploy function of the strategy
}

function _totalAssets() internal view virtual override returns (uint256 amount) {
    amount = _strategy.totalAssets(); // Calls the totalAssets function of the strategy
}
```
It is obvious that the return value should represent the amount of assets when `_strategy.deploy()`, `_strategy.undeploy()` or `_strategy.totalAssets()` is called.

However, the functions in `StrategySupplyERC4626` mistakenly return the number of shares other than the amount of underlying asset:
```solidity
/**
 * @inheritdoc StrategySupplyBase
 */
function _deploy(uint256 amount) internal override returns (uint256) {
    return _vault.deposit(amount, address(this));
}

/**
 * @inheritdoc StrategySupplyBase
 */
function _undeploy(uint256 amount) internal override returns (uint256) {
    return _vault.withdraw(amount, address(this), address(this));
}

/**
 * @inheritdoc StrategySupplyBase
 */
function _getBalance() internal view override returns (uint256) {
    return _vault.balanceOf(address(this));
}
```
This issue could lead to a scenario where a portion of user assets are permanently locked within the BakerFi vault. Create `ERC4626Mock` contract with below codes: 
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract ERC4626Mock is ERC4626 {
    constructor(IERC20 asset_) ERC4626(asset_) ERC20("Mock Vault", "MV") {
    }
}
```
Create `StrategySupplyERC4626.ts` with below codes and run `npm run test`:
```solidity
import { describeif } from '../../common';

import '@nomicfoundation/hardhat-ethers';
import { loadFixture } from '@nomicfoundation/hardhat-network-helpers';
import { expect } from 'chai';
import { ethers, network } from 'hardhat';
import {
  deployVaultRegistry,
  deployStEth,
  deployAaveV3,
  deployWETH,
  deployVault
} from '../../../scripts/common';
describeif(network.name === 'hardhat')('Strategy Supply ERC4626', function () {
  // Fixture to deploy contracts before each test
  async function deployStrategySupplyERC4626() {
    const [owner, otherAccount] = await ethers.getSigners();

    const BakerFiProxyAdmin = await ethers.getContractFactory('BakerFiProxyAdmin');
    const proxyAdmin = await BakerFiProxyAdmin.deploy(owner.address);
    await proxyAdmin.waitForDeployment();

    const MAX_SUPPLY = ethers.parseUnits('1000000000');
    const WETH = await ethers.getContractFactory('WETH');
    const weth = await WETH.deploy();
    await weth.waitForDeployment();
    // Deposit ETH
    await weth.deposit?.call('', { value: ethers.parseUnits('100', 18) });
    const ERC4626Vault = await ethers.getContractFactory("ERC4626Mock");
    const erc4626Vault = await ERC4626Vault.deploy(weth.getAddress());
    await erc4626Vault.waitForDeployment();

    // Deploy StrategySupply contract
    const StrategySupply = await ethers.getContractFactory('StrategySupplyERC4626');
    const strategy = await StrategySupply.deploy(
      owner.address,
      await weth.getAddress(),
      await erc4626Vault.getAddress(),
    );
    await strategy.waitForDeployment();

    const { proxy: vaultProxy } = await deployVault(
        owner.address,
        'Bread ETH',
        'brETH',
        await strategy.getAddress(),
        await weth.getAddress(),
        proxyAdmin,
    );
    await strategy.transferOwnership(await vaultProxy.getAddress());
    const vault = await ethers.getContractAt('Vault', await vaultProxy.getAddress());
    return { weth, strategy, owner, otherAccount, erc4626Vault, vault};
  }

  it.only('Deposit 10 ether but 5 ether can be withdrawn', async () => {
    const { weth, strategy, owner, otherAccount, erc4626Vault, vault } = await loadFixture(deployStrategySupplyERC4626);
    const tenEther  = ethers.parseEther('10');
    const fiveEther = ethers.parseEther('5');
    //@audit-info owner deposits 10e18 WETH into erc4626Vault
    await weth.approve(erc4626Vault.getAddress(), tenEther);
    await erc4626Vault.deposit(tenEther, owner.address);
    //@audit-info 10e18 shares are minted to owner
    expect(await erc4626Vault.balanceOf(owner.address)).to.equal(tenEther);
    //@audit-info transfer 10e18 WETH to erc4626Vault  
    await weth.transfer(erc4626Vault.getAddress(), tenEther);
    //@audit-info erc4646Vault has 20e18 WETH with total supply of 10e18 shares
    expect(await weth.balanceOf(erc4626Vault.getAddress())).to.equal(ethers.parseEther('20'));
    expect(await erc4626Vault.totalSupply()).to.equal(ethers.parseEther('10'));
    //@audit-info owner deposits 10e18 WETH into vault
    await vault.enableAccount(owner.address, true);
    await weth.approve(vault.getAddress(), tenEther);
    await vault.deposit(tenEther, owner.address);
    //@audit-info however, only 5e18 WETH can be withdrawn, the rest 5e18 WETH will be locked forever
    expect(await vault.maxWithdraw(owner.address)).to.equal(fiveEther);
  });
});
```
As we can see that only 5e18 WETH can be withdrawn within 10e18 WETH deployed. The rest 5e18 WETH are permanently locked within the BakerFi vault. The amount of locked asset can be calculated as below:

_Note: please see scenario in warden’s[original submission](https://code4rena.com/evaluate/2024-12-bakerfi-invitational/submissions/F-1)._

## Recommendation

No recommendation

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mis‑reporting of values inside a strategy that supplies assets to a vault. The strategy’s internal functions that are supposed to return the amount of underlying tokens mistakenly return the number of vault shares instead. Because the vault’s core accounting logic expects asset amounts from these calls, it uses share counts as if they were token quantities. This mismatch causes the vault to calculate a smaller withdrawable amount than the actual deposited assets. When a user deposits a certain quantity of tokens, the vault records the deposit correctly but later, during withdrawal, the conversion from shares back to assets uses the wrong basis, resulting in only a fraction of the deposited tokens being considered withdrawable. The remaining tokens stay locked in the vault because the accounting state believes they have already been accounted for by the (incorrect) share values. The issue manifests whenever the strategy is used by any BakerFi vault that relies on the faulty functions, i.e., on every deposit and withdrawal operation. It affects all users of the affected vaults, the protocol’s overall liquidity, and any downstream contracts that assume correct asset accounting. The bug was discovered during a formal audit by reviewing the implementation of the strategy’s internal methods and observing that they returned share balances rather than asset amounts, which was confirmed by a test that deposited ten ether and could only withdraw five ether. The problem is subtle because the contract still mints and burns shares correctly, so the UI may show a normal deposit, but the withdrawal limits appear unexpectedly low, making the loss of funds easy to miss. The impact is a permanent lock of a portion of user assets, effectively reducing the usable balance and potentially causing financial loss. To fix the issue, the strategy’s internal functions must be changed to return true asset quantities – the amount of underlying tokens transferred or held – and the vault’s total‑assets query must also reflect the real token balance. In other words, the accounting layer must be aligned so that share‑to‑asset conversions use the correct underlying amounts, restoring accurate max‑withdraw calculations and preventing assets from becoming irretrievable.
