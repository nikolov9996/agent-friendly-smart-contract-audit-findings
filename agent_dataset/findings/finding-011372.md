---
id: 11372
severity: "High"
---

# Vaults weth reward is not distributed correctly

## Description

When market receives fee in weth, wethRewardPerVaultShare is incremented by receivedVaultWethReward amount. However, as its name suggests, wethRewardPerVaultShare is reward per share, so it should be incremented by receivedVaultWethReward / totalDelegatedCreditUsd.

This inconsistency inflates vault.wethRewardDistribution.valuePerShare and effectively inflates amount to claim in FeeDistributionBranch.claimFees

Root Cause Analysis
MarketMakingEngine can receive market fee from registered engines via FeeDistributionBranch.receiveMarketFee

```solidity
function receiveMarketFee(
        uint128 marketId,
        address asset,
        uint256 amount
    )
    external
    onlyRegisteredEngine(marketId)
```

When asset is weth, it distributes weth reward to protocol fee recipients and vaults:

```solidity
if (asset == MarketMakingEngineConfiguration.load().weth) {
    // if asset is weth, we can skip straight to handling the weth reward distribution
    _handleWethRewardDistribution(market, address(0), amountX18);
}
```

In _handleWethRewardDistribution, received weth amount is split to receivedProtocolWethReward and receivedVaultsWethReward. Split logic is like the following:

```solidity
receivedProtocolWethReward = receivedWeth * feeRecipientsShares
receivedVaultsWethReward = receivedWeth - receivedProtocolWethReward
```

receivedProtocolWethReward is for protocol fee recipients' weth reward, and receivedVaultsWethReward is for vault's LPs' weth reward.

And after that, inside Market.receiveWethReward, the following happens:

```solidity
// increment the amount of pending weth reward to be distributed to fee recipients
self.availableProtocolWethReward =
    ud60x18(self.availableProtocolWethReward).add(receivedProtocolWethRewardX18).intoUint128();
// increment the all time weth reward storage
self.wethRewardPerVaultShare =
    ud60x18(self.wethRewardPerVaultShare).add(receivedVaultsWethRewardX18).intoUint128();
```

So whenever the market receive weth fee, wethRewardPerVaultShare is incremented by the weth fee amount. However, as the name suggests, it represents vaule per vault share, so it should be divided by totalDelegatedCreditUsd.

We can validate the above statement by comparing wethRewardPerVaultShare to similar attributes realizedDebtUsdPerVaultShare and unrealizedDebtUsdPerVaultShare:

```solidity
SD59x18 totalVaultSharesX18 = ud60x18(self.totalDelegatedCreditUsd).intoSD59x18();
...
// @audit realizedDebtUsdPerVaultShare and unrealizedDebtUsdPerVaultShare are divided by totalDelegatedCreditUsd
// and later be multiplied by vault delegated credit share
self.realizedDebtUsdPerVaultShare = newRealizedDebtUsdX18.div(totalVaultSharesX18).intoInt256().toInt128();
self.unrealizedDebtUsdPerVaultShare = newUnrealizedDebtUsdX18.div(totalVaultSharesX18).intoInt256().toInt128();
```

This inconsistency inflates Vault.wethRewardDistribution.vaulePerShare during Vault.recalculateVaultsCreditCapacity:

```solidity
// inside Market.getVaultAccumulatedValues
UD60x18 vaultCreditShareX18 = vaultDelegatedCreditUsdX18.div(getTotalDelegatedCreditUsd(self));
...
 // @audit realizedDebtChangeUsd = ΔrealizedDebtUsdPerVaultShare * vaultCreditShareX18
realizedDebtChangeUsdX18 = !lastVaultDistributedRealizedDebtUsdPerShareX18.isZero()
            ? sd59x18(self.realizedDebtUsdPerVaultShare).sub(lastVaultDistributedRealizedDebtUsdPerShareX18).mul(
                vaultCreditShareX18.intoSD59x18()
            )
            : SD59x18_ZERO;
...
// @audit however wethRewardChange is just ΔvaultWethReward
wethRewardChangeX18 = ud60x18(self.wethRewardPerVaultShare).sub(lastVaultDistributedWethRewardPerShareX18);

// inside Vault.recalculateVaultsCreditCapacity
// distributes the vault's total WETH reward change, earned from its connected markets
if (!vaultTotalWethRewardChangeX18.isZero() && self.wethRewardDistribution.totalShares != 0) {
    SD59x18 vaultTotalWethRewardChangeSD59X18 =
        sd59x18(int256(vaultTotalWethRewardChangeX18.intoUint256()));
    // @audit this wethRewardChange is distributed to actors per actor share
    self.wethRewardDistribution.distributeValue(vaultTotalWethRewardChangeSD59X18);
}
```

So what happens is:
✔️ Market's realizedDebt is distributed to vaults propotionally according to each vault's delegated credit USD
 ❌ Market's weth reward is copied to every vaults. i.e all connected vaults' total weth reward will be numberOfVaults * wethReward

## Proof of Concept

PoC will demonstrate the following scenario:
A market is connected to 2 vaults
Each vault has only one actor with 1 share
It received 1 WETH
Weth to be distributed in one vault is calculated like wethDistribution.valuePerShare * wethDistribution.totalShares
The sum of weth to be distributed in two vaults is 2 WETH, where expected value is 1 WETH

```solidity
pragma solidity 0.8.25;

import { CreditDelegationBranch } from "@zaros/market-making/branches/CreditDelegationBranch.sol";
import { VaultRouterBranch } from "@zaros/market-making/branches/VaultRouterBranch.sol";
import { MarketMakingEngineConfigurationBranch } from
    "@zaros/market-making/branches/MarketMakingEngineConfigurationBranch.sol";
import { Vault } from "@zaros/market-making/leaves/Vault.sol";
import { Market } from "@zaros/market-making/leaves/Market.sol";
import { CreditDelegation } from "@zaros/market-making/leaves/CreditDelegation.sol";
import { Distribution } from "@zaros/market-making/leaves/Distribution.sol";
import { MarketMakingEngineConfiguration } from "@zaros/market-making/leaves/MarketMakingEngineConfiguration.sol";
import { LiveMarkets } from "@zaros/market-making/leaves/LiveMarkets.sol";
import { Collateral } from "@zaros/market-making/leaves/Collateral.sol";
import { UD60x18, ud60x18 } from "@prb-math/UD60x18.sol";
import { SD59x18, sd59x18 } from "@prb-math/SD59x18.sol";
import { Constants } from "@zaros/utils/Constants.sol";
import { SafeCast } from "@openzeppelin/utils/math/SafeCast.sol";
import { EnumerableMap } from "@openzeppelin/utils/structs/EnumerableMap.sol";
import { EnumerableSet } from "@openzeppelin/utils/structs/EnumerableSet.sol";
import { IERC4626 } from "@openzeppelin/token/ERC20/extensions/ERC4626.sol";
import { Errors } from "@zaros/utils/Errors.sol";

import "forge-std/Test.sol";

uint256 constant DEFAULT_DECIMAL = 18;

contract MockVault {
    function totalAssets() external pure returns (uint256) {
        return 1000 * (10 ** DEFAULT_DECIMAL);
    }
}

contract MockPriceAdapter {
    function getPrice() external pure returns (uint256) {
        return 10 ** DEFAULT_DECIMAL;
    }
}

contract MockEngine {
    function getUnrealizedDebt(uint128) external pure returns (int256) {
        return 0;
    }
}

contract WethRewardDistributionTest is
    CreditDelegationBranch,
    VaultRouterBranch,
    MarketMakingEngineConfigurationBranch,
    Test
{
    using Vault for Vault.Data;
    using Market for Market.Data;
    using CreditDelegation for CreditDelegation.Data;
    using Collateral for Collateral.Data;
    using SafeCast for uint256;
    using EnumerableSet for EnumerableSet.UintSet;
    using EnumerableMap for EnumerableMap.AddressToUintMap;
    using LiveMarkets for LiveMarkets.Data;
    using MarketMakingEngineConfiguration for MarketMakingEngineConfiguration.Data;
    using Distribution for Distribution.Data;

    uint128 marketId = 1;
    address asset = vm.addr(1);
    address usdc = vm.addr(2);
    address weth = vm.addr(3);
    uint256 collateralAssetAmount = 100 * (10 ** DEFAULT_DECIMAL);
    uint256 usdcAmount = 200 * (10 ** DEFAULT_DECIMAL);
    uint256 creditRatio = 0.8e18;
    uint256[] vaultIds = new uint256[](2);

    function setUp() external {
        MockVault indexToken = new MockVault();
        MockPriceAdapter priceAdapter = new MockPriceAdapter();
        MockEngine mockEngine = new MockEngine();

        MarketMakingEngineConfiguration.Data storage configuration = MarketMakingEngineConfiguration.load();
        configuration.usdc = usdc;

        Market.Data storage market = Market.load(marketId);
        market.engine = address(mockEngine);
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vaultIds[0] = 1;
        vaultIds[1] = 2;
        market.id = marketId;

        LiveMarkets.Data storage liveMarkets = LiveMarkets.load();
        liveMarkets.addMarket(marketId);

        Collateral.Data storage collateral = Collateral.load(asset);
        collateral.priceAdapter = address(priceAdapter);
        collateral.creditRatio = creditRatio;

        for (uint128 vaultId = 1; vaultId <= 2; vaultId++) {
            Vault.Data storage vault = Vault.load(vaultId);
            vault.id = vaultId;
            vault.indexToken = address(indexToken);
            vault.collateral.decimals = uint8(DEFAULT_DECIMAL);
            vault.collateral.priceAdapter = address(priceAdapter);
            vault.collateral.creditRatio = creditRatio;
            vault.wethRewardDistribution.setActorShares(bytes32(0), ud60x18(1e18));
        }
        _connectVaultsAndMarkets();
    }

    function testWethRewardDistribution() external {
        uint256 wethRewardAmount = 1e18;

        _recalculateVaultsCreditCapacity();
        Market.Data storage market = Market.load(marketId);
        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100e18));
        // Market has received 1 WETH vault reward
        market.receiveWethReward(weth, ud60x18(0), ud60x18(wethRewardAmount));
        _recalculateVaultsCreditCapacity();

        uint256 totalWethToDistribute;
        for (uint128 vaultId = 1; vaultId <= 2; vaultId++) {
            Vault.Data storage vault = Vault.load(vaultId);
            Distribution.Data storage distribution = vault.wethRewardDistribution;
            assertGt(distribution.valuePerShare, 0);
            totalWethToDistribute +=
                ud60x18(distribution.totalShares).mul(ud60x18(uint256(distribution.valuePerShare))).unwrap();
        }
        // totalWethToDistribute is 2 WETH
        assertEq(totalWethToDistribute, wethRewardAmount * 2);
    }

    function _connectVaultsAndMarkets() internal {
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        uint256[] memory _vaultIds = vaultIds;
        vm.startPrank(address(0));
        WethRewardDistributionTest(address(this)).connectVaultsAndMarkets(marketIds, _vaultIds);
        vm.stopPrank();
    }

    function _recalculateVaultsCreditCapacity() internal {
        WethRewardDistributionTest(address(this)).updateMarketCreditDelegations(marketId);
    }
}
LP stakers claim more weth reward than expected
Late fee claimers might not receive weth reward as it is already depleted

## Recommendation

We can consider the following patch:

```diff
diff --git a/src/market-making/leaves/Market.sol b/src/market-making/leaves/Market.sol
index 9d5bf8d..006d445 100644
--- a/src/market-making/leaves/Market.sol
+++ b/src/market-making/leaves/Market.sol
@@ -318,7 +318,9 @@ library Market {
             : UD60x18_ZERO;
 
         // TODO: fix the vaultCreditShareX18 flow to multiply by wethRewardChangeX18
wethRewardChangeX18 = ud60x18(self.wethRewardPerVaultShare).sub(lastVaultDistributedWethRewardPerShareX18);
wethRewardChangeX18 = ud60x18(self.wethRewardPerVaultShare).sub(lastVaultDistributedWethRewardPerShareX18).mul(
vaultCreditShareX18
);
     }
 
     /// @notice Returns whether the market has reached the auto deleverage start threshold, i.e, if the ADL system
@@ -521,7 +523,8 @@ library Market {
             ud60x18(self.availableProtocolWethReward).add(receivedProtocolWethRewardX18).intoUint128();
 
         // increment the all time weth reward storage
self.wethRewardPerVaultShare =
ud60x18(self.wethRewardPerVaultShare).add(receivedVaultsWethRewardX18).intoUint128();
self.wethRewardPerVaultShare = ud60x18(self.wethRewardPerVaultShare).add(receivedVaultsWethRewardX18).div(
self.totalDelegatedCreditUsd
).intoUint128();
     }
 }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect handling of the WETH reward accounting in the market‑making engine. When a market receives a fee in WETH, the contract adds the raw fee amount to the variable that is meant to represent reward per vault share (wethRewardPerVaultShare). Because the variable name implies a per‑share value, the amount should be divided by the total delegated credit in USD before being stored, but the implementation adds the full amount directly. This mistake causes the per‑share reward to be inflated, so every vault that is linked to the market receives the entire fee amount instead of a proportionate slice based on its delegated credit. The inflated per‑share value propagates to the vault’s internal distribution logic, where the vault multiplies the valuePerShare by its total shares, resulting in each vault’s actors claiming more WETH than actually deposited. The impact is that liquidity providers see higher than expected WETH rewards, while the protocol’s reward pool can be drained prematurely, breaking the accounting guarantees of the system. The bug manifests whenever a market processes a WETH fee and has at least one connected vault with a non‑zero totalDelegatedCreditUsd. All vaults, regardless of size, receive the full fee, violating the intended proportional distribution model. The issue was uncovered during a security audit that included a proof‑of‑concept test where two vaults each with a single share claimed a total of two WETH after a single WETH fee was sent to the market. The problem is subtle because the variable name and surrounding code suggest a per‑share calculation, and the missing division is easy to overlook amidst similar correctly‑implemented per‑share metrics such as realizedDebtUsdPerVaultShare. To remediate, the contract should divide the receivedVaultsWethReward by totalDelegatedCreditUsd when updating wethRewardPerVaultShare, and the vault recalculation routine should apply the same proportional factor when distributing the reward change, ensuring that each vault receives a share that matches its credit contribution. This correction restores the intended accounting logic, prevents reward inflation, and protects both users and the protocol from unintended loss of funds.
