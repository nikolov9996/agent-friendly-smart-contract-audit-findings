---
id: 11371
severity: "High"
---

# Underflow when updating credit delegation will result protocol DoS

## Description

If vault's credit delegation USD is decreasing, there will be underflow when calculating credit delta. This will result in protocol DoS.

Root Cause Analysis
We have the following code base in Vault._updateCreditDelegations:

```solidity
UD60x18 creditDeltaUsdX18 = newCreditDelegationUsdX18.sub(previousCreditDelegationUsdX18);
```

Here, newCreditDelegationUsdX18 and previousCreditDelegationUsdX18 are all UD60x18 type, which means, it will underflow when newCreditDelegationUsdX18 < previousCreditDelegationUsdX18

So when is newCreditDelegationUsdX18 < previousCreditDelegationUsdX18?

Let's look at the following code:

```solidity
// stores the vault's total credit capacity to be returned
vaultCreditCapacityUsdX18 = getTotalCreditCapacityUsd(self);

// if the vault's credit capacity went to zero or below, we set its credit delegation to that market
// to zero
UD60x18 newCreditDelegationUsdX18 = vaultCreditCapacityUsdX18.gt(SD59x18_ZERO)
    ? vaultCreditCapacityUsdX18.intoUD60x18().mul(creditDelegationShareX18)
    : UD60x18_ZERO;
```

We can derive that creditDelegationUsd is calculated as the following:

$creditDelegationUsd = totalCreditCapacity * creditDelegationShare$

where totalCreditCapacity is calculated as the following:

$totalCreditCapcity = totalAssetsUsd - vaultMarketsRealizedDebtUsd + depositedUsdc - vaultMarketsUnrealizedDebtUsd$

So newCreditDelegationUsd can be lower than previousCreditDelegationUsd in the following scenarios:
Collateral price is decreased (totalAssetsUsdis decreased)
An LP has redeemed some share (totalAssetsUsdis decreased)
creditDelegationShare is decreased
vaultMarketsRealizedDebtUsd is increased
vaultMarketsUnrealizedDebtUsd is increased
depositedUsdc is decreased

So, it can happen very frequently.

PoC
The following POC demonstrates an underflow when collateral price is dropped:

```solidity
pragma solidity 0.8.25;

import { CreditDelegationBranch } from "@zaros/market-making/branches/CreditDelegationBranch.sol";
import { VaultRouterBranch } from "@zaros/market-making/branches/VaultRouterBranch.sol";
import { MarketMakingEngineConfigurationBranch } from
    "@zaros/market-making/branches/MarketMakingEngineConfigurationBranch.sol";
import { Vault } from "@zaros/market-making/leaves/Vault.sol";
import { Market } from "@zaros/market-making/leaves/Market.sol";
import { CreditDelegation } from "@zaros/market-making/leaves/CreditDelegation.sol";
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
    uint256 price = 10 ** DEFAULT_DECIMAL;

    function getPrice() external view returns (uint256) {
        return price;
    }

    function setPrice(uint256 newPrice) external {
        price = newPrice;
    }
}

contract MockEngine {
    function getUnrealizedDebt(uint128) external pure returns (int256) {
        return 0;
    }
}

contract MarketMakingConfigurationBranchTest is
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

    uint128 marketId = 1;
    uint128 vaultId = 1;
    address asset = vm.addr(1);
    address usdc = vm.addr(2);
    address weth = vm.addr(3);
    uint256 collateralAssetAmount = 1000 * (10 ** DEFAULT_DECIMAL);
    uint256 creditRatio = 1e18;
    MockPriceAdapter priceAdapter;

    uint256[] vaultIds = new uint128[](1);

    function setUp() external {
        MockVault indexToken = new MockVault();
        priceAdapter = new MockPriceAdapter();
        MockEngine mockEngine = new MockEngine();

        MarketMakingEngineConfiguration.Data storage configuration = MarketMakingEngineConfiguration.load();
        configuration.usdc = usdc;

        Market.Data storage market = Market.load(marketId);
        market.engine = address(mockEngine);
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vaultIds[0] = uint256(vaultId);
        market.id = marketId;

        LiveMarkets.Data storage liveMarkets = LiveMarkets.load();
        liveMarkets.addMarket(marketId);

        Collateral.Data storage collateral = Collateral.load(asset);
        collateral.priceAdapter = address(priceAdapter);
        collateral.creditRatio = creditRatio;

        Vault.Data storage vault = Vault.load(vaultId);
        vault.id = vaultId;
        vault.indexToken = address(indexToken);
        vault.collateral.decimals = uint8(DEFAULT_DECIMAL);
        vault.collateral.priceAdapter = address(priceAdapter);
        vault.collateral.creditRatio = creditRatio;

        uint256[] memory _vaultIds = vaultIds;
        connectVaultsAndMarkets(vaultIds);
    }

    function testRevertWhenCreditDepositDrop() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        CreditDelegation.Data storage creditDelegation = CreditDelegation.load(vaultId, uint256(marketId));
        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(300e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();

        priceAdapter.setPrice(0.9e18); // price dropped from 1 usd to 0.9 usd

        vm.expectRevert(stdError.arithmeticError);
        _recalculateVaultsCreditCapacity();
    }

    function connectVaultsAndMarkets(uint256[] memory vaultIds) internal {
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vm.startPrank(address(0));
        MarketMakingConfigurationBranchTest(address(this)).connectVaultsAndMarkets(marketIds, _vaultIds);
        vm.stopPrank();
    }

    function _recalculateVaultsCreditCapacity() internal {
        MarketMakingConfigurationBranchTest(address(this)).updateMarketCreditDelegations(marketId);
    }
}
```

Since most of the protocol's functionalities rely on Vault.recalculateVaultsCreditCapacity, this underflow will bring frequent DoS to the protocol.

For example: LP deposit, withdraw, stake, unstake, weth reward distribution won't be working due to revert in recalculation.

## Proof of Concept

The following POC demonstrates an underflow when collateral price is dropped:

```solidity
pragma solidity 0.8.25;

import { CreditDelegationBranch } from "@zaros/market-making/branches/CreditDelegationBranch.sol";
import { VaultRouterBranch } from "@zaros/market-making/branches/VaultRouterBranch.sol";
import { MarketMakingEngineConfigurationBranch } from
    "@zaros/market-making/branches/MarketMakingEngineConfigurationBranch.sol";
import { Vault } from "@zaros/market-making/leaves/Vault.sol";
import { Market } from "@zaros/market-making/leaves/Market.sol";
import { CreditDelegation } from "@zaros/market-making/leaves/CreditDelegation.sol";
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
    uint256 price = 10 ** DEFAULT_DECIMAL;

    function getPrice() external view returns (uint256) {
        return price;
    }

    function setPrice(uint256 newPrice) external {
        price = newPrice;
    }
}

contract MockEngine {
    function getUnrealizedDebt(uint128) external pure returns (int256) {
        return 0;
    }
}

contract MarketMakingConfigurationBranchTest is
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

    uint128 marketId = 1;
    uint128 vaultId = 1;
    address asset = vm.addr(1);
    address usdc = vm.addr(2);
    address weth = vm.addr(3);
    uint256 collateralAssetAmount = 1000 * (10 ** DEFAULT_DECIMAL);
    uint256 creditRatio = 1e18;
    MockPriceAdapter priceAdapter;

    uint256[] vaultIds = new uint128[](1);

    function setUp() external {
        MockVault indexToken = new MockVault();
        priceAdapter = new MockPriceAdapter();
        MockEngine mockEngine = new MockEngine();

        MarketMakingEngineConfiguration.Data storage configuration = MarketMakingEngineConfiguration.load();
        configuration.usdc = usdc;

        Market.Data storage market = Market.load(marketId);
        market.engine = address(mockEngine);
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vaultIds[0] = uint256(vaultId);
        market.id = marketId;

        LiveMarkets.Data storage liveMarkets = LiveMarkets.load();
        liveMarkets.addMarket(marketId);

        Collateral.Data storage collateral = Collateral.load(asset);
        collateral.priceAdapter = address(priceAdapter);
        collateral.creditRatio = creditRatio;

        Vault.Data storage vault = Vault.load(vaultId);
        vault.id = vaultId;
        vault.indexToken = address(indexToken);
        vault.collateral.decimals = uint8(DEFAULT_DECIMAL);
        vault.collateral.priceAdapter = address(priceAdapter);
        vault.collateral.creditRatio = creditRatio;

        uint256[] memory _vaultIds = vaultIds;
        connectVaultsAndMarkets(vaultIds);
    }

    function testRevertWhenCreditDepositDrop() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        CreditDelegation.Data storage creditDelegation = CreditDelegation.load(vaultId, uint256(marketId));
        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(300e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();

        priceAdapter.setPrice(0.9e18); // price dropped from 1 usd to 0.9 usd

        vm.expectRevert(stdError.arithmeticError);
        _recalculateVaultsCreditCapacity();
    }

    function connectVaultsAndMarkets(uint256[] memory vaultIds) internal {
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vm.startPrank(address(0));
        MarketMakingConfigurationBranchTest(address(this)).connectVaultsAndMarkets(marketIds, _vaultIds);
        vm.stopPrank();
    }

    function _recalculateVaultsCreditCapacity() internal {
        MarketMakingConfigurationBranchTest(address(this)).updateMarketCreditDelegations(marketId);
    }
}
```

## Recommendation

SD59x18 type should be used for creditDeltaX18 calculation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic underflow that occurs when the protocol updates a vault’s credit delegation amount using an unsigned fixed‑point type (UD60x18) and subtracts the previous delegation from the newly calculated delegation. Because the subtraction is performed with an unsigned type, if the new delegation value is lower than the previous one the operation wraps around to a very large number, triggering a Solidity arithmetic error and causing the whole credit‑capacity recalculation to revert. The root cause is the misuse of an unsigned type for a value that can legitimately become negative when the vault’s credit capacity decreases – for example when the collateral price falls, an LP withdraws assets, the credit‑delegation share is reduced, realized or unrealized debt rises, or deposited USDC is removed. Under these conditions the new credit delegation can be smaller than the old one, which happens frequently in normal market operations. An attacker does not need to craft a special exploit; any legitimate market event that reduces the vault’s credit capacity will automatically cause the underflow and abort the transaction. The impact is a denial‑of‑service: all functions that rely on the vault’s credit‑capacity recalculation – deposits, withdrawals, staking, unstaking, and reward distribution – revert, leaving users unable to interact with the protocol and potentially freezing liquidity. The issue affects every participant that uses the affected vaults, including liquidity providers, borrowers, and the protocol itself, because core accounting logic is broken. It was discovered during a formal audit by executing a test that lowered the collateral price, which caused the contract to revert with a standard arithmetic error. The bug is hard to notice because the calculation appears correct under normal growth conditions; only when the value moves in the opposite direction does the underflow surface, and the revert message does not directly point to the underlying logic error. The proper fix is to perform the delta calculation with a signed fixed‑point type (SD59x18) or to add explicit checks that prevent subtraction when the result would be negative, thereby aligning the arithmetic with the business rule that credit delegation may decrease. In generic terms, this is an unsigned integer underflow caused by a signed‑unsigned mismatch in a financial accounting routine, violating the protocol’s invariant that credit capacity must always be a non‑negative, correctly tracked amount. From a user’s perspective, actions that previously succeeded now revert with an “arithmetic error”, leading to expectations of a successful deposit or reward claim being unmet, and balances appearing unchanged while the UI shows no progress. The failure mode is effectively “funds disappear” in the sense that operations cannot be completed, not that assets are stolen, but the protocol’s accounting is halted until the bug is corrected.
