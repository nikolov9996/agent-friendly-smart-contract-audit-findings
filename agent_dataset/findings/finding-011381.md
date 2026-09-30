---
id: 11381
severity: "High"
---

# Markets and vaults will not update their state until market fee is received, any deposits before market fee will not be reflected

## Description

When calculating accumulated vault values, the change is not acknowledged if previous value is zero. This will prevent some important values from getting updated.

Root Cause
During Vault.recalculateVaultsCreditCapacity, we have the following code Market.getVaultAccumulatedValues:

```solidity
realizedDebtChangeUsdX18 = !lastVaultDistributedRealizedDebtUsdPerShareX18.isZero()
    ? sd59x18(self.realizedDebtUsdPerVaultShare).sub(lastVaultDistributedRealizedDebtUsdPerShareX18).mul(
        vaultCreditShareX18.intoSD59x18()
    )
    : SD59x18_ZERO;

unrealizedDebtChangeUsdX18 = !lastVaultDistributedUnrealizedDebtUsdPerShareX18.isZero()
    ? sd59x18(self.unrealizedDebtUsdPerVaultShare).sub(lastVaultDistributedUnrealizedDebtUsdPerShareX18).mul(
        vaultCreditShareX18.intoSD59x18()
    )
    : SD59x18_ZERO;

usdcCreditChangeX18 = !lastVaultDistributedUsdcCreditPerShareX18.isZero()
    ? ud60x18(self.usdcCreditPerVaultShare).sub(lastVaultDistributedUsdcCreditPerShareX18).mul(
        vaultCreditShareX18
    )
    : UD60x18_ZERO;

// TODO: fix the vaultCreditShareX18 flow to multiply by wethRewardChangeX18
wethRewardChangeX18 = ud60x18(self.wethRewardPerVaultShare).sub(lastVaultDistributedWethRewardPerShareX18);
```

It has a strange assumption that if the previous value is zero, the change is also zero.

These "lastVaultDistributed"-values are coming from vault-market creditDelegation, and since creditDelegation can not be initialized, all "lastVaultDistributed"-values will start from 0.

This means realizedDebtChangeUsdX18, unrealizedDebtChangeUsdX18, usdcCreditChangeX18 will all be 0.

We also have the following:

```javascript
if (
    ctx.realizedDebtChangeUsdX18.isZero() && ctx.unrealizedDebtChangeUsdX18.isZero()
        && ctx.usdcCreditChangeX18.isZero() && ctx.wethRewardChangeX18.isZero()
) {
    continue;
}
```

So if wethRewardChangeX18 is also zero, all market and vault's state vars won't be updated!

Luckily, such zero-check is not done for weth reward, so as soon as the market receives some weth fee, it will start to update the other values. But all deposits before the weth reward won't be reflected.

PoC
PoC demonstrates calculation inconsistency between two cases:
damnMuchDepositThenSmallDeposit
100M usdc is deposited to market
Market receives weth reward
Recalculate vaults' capacity
100 usdc is deposited to market
smallDepositThenDamnMuchDeposit
100 usdc is deposited to market
Market receives weth reward
Recalculate vaults' capacity
100M usdc is deposited to market

Although the total sum of deposited usdc is the same (100M + 100), market and vault's states will be vastly different between two scenarios:

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
    function getPrice() external pure returns (uint256) {
        return 10 ** DEFAULT_DECIMAL;
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
    uint256 collateralAssetAmount = 100 * (10 ** DEFAULT_DECIMAL);
    uint256 usdcAmount = 200 * (10 ** DEFAULT_DECIMAL);
    uint256 creditRatio = 0.8e18;

    uint256[] vaultIds = new uint256[](1);

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

    function testDamnMuchDepositThenSmallDeposit() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100000000e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();
        market.settleCreditDeposit(usdc, ud60x18(100e18));
        _recalculateVaultsCreditCapacity();

        _logStates();
    }

    function testSmallDepositThenDamnMuchDeposit() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();
        market.settleCreditDeposit(usdc, ud60x18(100000000e18));
        _recalculateVaultsCreditCapacity();

        _logStates();
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

    function _logStates() internal {
        console.log("\n");
        _logMarketState();
        _logVaultState();
        _logCreditDelegationState();
        console.log("\n");
    }

    function _logMarketState() internal {
        Market.Data storage market = Market.load(marketId);
        UD60x18 creditDepositsValueUsdX18 = market.getCreditDepositsValueUsd();
        SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();
        UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();
        SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

        emit log_named_decimal_uint(
            "market.creditDepositsValueUsd", creditDepositsValueUsdX18.unwrap(), DEFAULT_DECIMAL
        );
        emit log_named_decimal_int("market.totalDebtUsd", marketTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("market.delegatedCreditUsd", delegatedCreditUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("market.creditCapacityUsd", creditCapacityUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int(
            "market.realizedDebtUsdPerVaultShare", market.realizedDebtUsdPerVaultShare, DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "market.usdcCreditPerVaultShare", uint256(market.usdcCreditPerVaultShare), DEFAULT_DECIMAL
        );
    }

    function _logVaultState() internal {
        Vault.Data storage vault = Vault.load(vaultId);
        SD59x18 vaultTotalDebtUsdX18 = vault.getTotalDebt();
        SD59x18 vaultTotalCreditCapacityX18 = vault.getTotalCreditCapacityUsd();
        emit log_named_decimal_int("vault.totalDebtUsd", vaultTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("vault.depositedUsdc", uint256(vault.depositedUsdc), DEFAULT_DECIMAL);
        emit log_named_decimal_int("vault.totalCreditCapacity", vaultTotalCreditCapacityX18.unwrap(), DEFAULT_DECIMAL);
    }

    function _logCreditDelegationState() internal {
        CreditDelegation.Data storage creditDelegation = CreditDelegation.load(vaultId, uint256(marketId));
        emit log_named_decimal_uint("creditDelegation.valueUsd", uint256(creditDelegation.valueUsd), DEFAULT_DECIMAL);
        emit log_named_decimal_int(
            "creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare",
            int256(creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare),
            DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "creditDelegation.lastVaultDistributedUsdcCreditPerShare",
            uint256(creditDelegation.lastVaultDistributedUsdcCreditPerShare),
            DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "creditDelegation.lastVaultDistributedWethRewardPerShare",
            uint256(creditDelegation.lastVaultDistributedWethRewardPerShare),
            DEFAULT_DECIMAL
        );
    }
}
```

Console Output

```console
[PASS] testDamnMuchDepositAfterSmallDeposit() (gas: 480781)
Logs:

  market.creditDepositsValueUsd: 80.000000000000000000
  market.totalDebtUsd: 80.000000000000000000
  market.delegatedCreditUsd: 800.125000000000000000
  market.creditCapacityUsd: 880.125000000000000000
  market.realizedDebtUsdPerVaultShare: 0.100000000000000000
  market.usdcCreditPerVaultShare: 125000.125000000000000000
  vault.totalDebtUsd: -0.125000000000000000
  vault.depositedUsdc: 0.125000000000000000
  vault.totalCreditCapacity: 800.125000000000000000
  creditDelegation.valueUsd: 800.125000000000000000
  creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare: 0.100000000000000000
  creditDelegation.lastVaultDistributedUsdcCreditPerShare: 125000.125000000000000000
  creditDelegation.lastVaultDistributedWethRewardPerShare: 1.000000000000000000

[PASS] testSmallDepositAfterDamnMuchDeposit() (gas: 480727)
Logs:

  market.creditDepositsValueUsd: 80.000000000000000000
  market.totalDebtUsd: 80.000000000000000000
  market.delegatedCreditUsd: 125800.000000000000000000
  market.creditCapacityUsd: 125880.000000000000000000
  market.realizedDebtUsdPerVaultShare: 0.100000000000000000
  market.usdcCreditPerVaultShare: 125000.125000000000000000
  vault.totalDebtUsd: -125000.000000000000000000
  vault.depositedUsdc: 125000.000000000000000000
  vault.totalCreditCapacity: 125800.000000000000000000
  creditDelegation.valueUsd: 125800.000000000000000000
  creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare: 0.100000000000000000
  creditDelegation.lastVaultDistributedUsdcCreditPerShare: 125000.125000000000000000
  creditDelegation.lastVaultDistributedWethRewardPerShare: 1.000000000000000000
```

Protocol is in invalid state. This will affect swap index ratio and usd token swap ratio, which will ultimately lead to end user's fund loss and protocol's reputation damage.

## Proof of Concept

PoC demonstrates calculation inconsistency between two cases:
damnMuchDepositThenSmallDeposit
100M usdc is deposited to market
Market receives weth reward
Recalculate vaults' capacity
100 usdc is deposited to market
smallDepositThenDamnMuchDeposit
100 usdc is deposited to market
Market receives weth reward
Recalculate vaults' capacity
100M usdc is deposited to market

Although the total sum of deposited usdc is the same (100M + 100), market and vault's states will be vastly different between two scenarios:

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
    function getPrice() external pure returns (uint256) {
        return 10 ** DEFAULT_DECIMAL;
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
    uint256 collateralAssetAmount = 100 * (10 ** DEFAULT_DECIMAL);
    uint256 usdcAmount = 200 * (10 ** DEFAULT_DECIMAL);
    uint256 creditRatio = 0.8e18;

    uint256[] vaultIds = new uint256[](1);

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

    function testDamnMuchDepositThenSmallDeposit() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100000000e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();
        market.settleCreditDeposit(usdc, ud60x18(100e18));
        _recalculateVaultsCreditCapacity();

        _logStates();
    }

    function testSmallDepositThenDamnMuchDeposit() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();

        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100e18));
        market.receiveWethReward(weth, ud60x18(0), ud60x18(1e18));

        _recalculateVaultsCreditCapacity();
        market.settleCreditDeposit(usdc, ud60x18(100000000e18));
        _recalculateVaultsCreditCapacity();

        _logStates();
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

    function _logStates() internal {
        console.log("\n");
        _logMarketState();
        _logVaultState();
        _logCreditDelegationState();
        console.log("\n");
    }

    function _logMarketState() internal {
        Market.Data storage market = Market.load(marketId);
        UD60x18 creditDepositsValueUsdX18 = market.getCreditDepositsValueUsd();
        SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();
        UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();
        SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

        emit log_named_decimal_uint(
            "market.creditDepositsValueUsd", creditDepositsValueUsdX18.unwrap(), DEFAULT_DECIMAL
        );
        emit log_named_decimal_int("market.totalDebtUsd", marketTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("market.delegatedCreditUsd", delegatedCreditUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("market.creditCapacityUsd", creditCapacityUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int(
            "market.realizedDebtUsdPerVaultShare", market.realizedDebtUsdPerVaultShare, DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "market.usdcCreditPerVaultShare", uint256(market.usdcCreditPerVaultShare), DEFAULT_DECIMAL
        );
    }

    function _logVaultState() internal {
        Vault.Data storage vault = Vault.load(vaultId);
        SD59x18 vaultTotalDebtUsdX18 = vault.getTotalDebt();
        SD59x18 vaultTotalCreditCapacityX18 = vault.getTotalCreditCapacityUsd();
        emit log_named_decimal_int("vault.totalDebtUsd", vaultTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("vault.depositedUsdc", uint256(vault.depositedUsdc), DEFAULT_DECIMAL);
        emit log_named_decimal_int("vault.totalCreditCapacity", vaultTotalCreditCapacityX18.unwrap(), DEFAULT_DECIMAL);
    }

    function _logCreditDelegationState() internal {
        CreditDelegation.Data storage creditDelegation = CreditDelegation.load(vaultId, uint256(marketId));
        emit log_named_decimal_uint("creditDelegation.valueUsd", uint256(creditDelegation.valueUsd), DEFAULT_DECIMAL);
        emit log_named_decimal_int(
            "creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare",
            int256(creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare),
            DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "creditDelegation.lastVaultDistributedUsdcCreditPerShare",
            uint256(creditDelegation.lastVaultDistributedUsdcCreditPerShare),
            DEFAULT_DECIMAL
        );
        emit log_named_decimal_uint(
            "creditDelegation.lastVaultDistributedWethRewardPerShare",
            uint256(creditDelegation.lastVaultDistributedWethRewardPerShare),
            DEFAULT_DECIMAL
        );
    }
}
```

Console Output

```console
[PASS] testDamnMuchDepositAfterSmallDeposit() (gas: 480781)
Logs:

  market.creditDepositsValueUsd: 80.000000000000000000
  market.totalDebtUsd: 80.000000000000000000
  market.delegatedCreditUsd: 800.125000000000000000
  market.creditCapacityUsd: 880.125000000000000000
  market.realizedDebtUsdPerVaultShare: 0.100000000000000000
  market.usdcCreditPerVaultShare: 125000.125000000000000000
  vault.totalDebtUsd: -0.125000000000000000
  vault.depositedUsdc: 0.125000000000000000
  vault.totalCreditCapacity: 800.125000000000000000
  creditDelegation.valueUsd: 800.125000000000000000
  creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare: 0.100000000000000000
  creditDelegation.lastVaultDistributedUsdcCreditPerShare: 125000.125000000000000000
  creditDelegation.lastVaultDistributedWethRewardPerShare: 1.000000000000000000

[PASS] testSmallDepositAfterDamnMuchDeposit() (gas: 480727)
Logs:

  market.creditDepositsValueUsd: 80.000000000000000000
  market.totalDebtUsd: 80.000000000000000000
  market.delegatedCreditUsd: 125800.000000000000000000
  market.creditCapacityUsd: 125880.000000000000000000
  market.realizedDebtUsdPerVaultShare: 0.100000000000000000
  market.usdcCreditPerVaultShare: 125000.125000000000000000
  vault.totalDebtUsd: -125000.000000000000000000
  vault.depositedUsdc: 125000.000000000000000000
  vault.totalCreditCapacity: 125800.000000000000000000
  creditDelegation.valueUsd: 125800.000000000000000000
  creditDelegation.lastVaultDistributedRealizedDebtUsdPerShare: 0.100000000000000000
  creditDelegation.lastVaultDistributedUsdcCreditPerShare: 125000.125000000000000000
  creditDelegation.lastVaultDistributedWethRewardPerShare: 1.000000000000000000
```

## Recommendation

Consider removing strange zero check.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑update logic error in the market‑vault accounting module that prevents any vault or market variables from being refreshed until a WETH fee (the market reward) has been received. The root cause is a conditional expression that treats a previous per‑share distribution value of zero as an indication that the change for realized debt, unrealized debt and USDC credit is also zero, and then skips the entire update loop when all four change variables (realizedDebtChangeUsdX18, unrealizedDebtChangeUsdX18, usdcCreditChangeX18 and wethRewardChangeX18) are zero. Because the credit‑delegation structure is never initialized, the “lastVaultDistributed” values start at zero, causing the three USD‑related change variables to be forced to zero on the first accounting cycle. The code then checks if all four change variables are zero and continues without updating any market or vault state. Only when a non‑zero WETH reward arrives does wethRewardChangeX18 become non‑zero, breaking the early‑exit condition and allowing the other variables to be updated – but deposits that occurred before the first reward are never reflected in the vault’s depositedUsdc, totalDebt or totalCreditCapacity fields. This leads to inconsistent accounting: two sequences of deposits that sum to the same total (a large deposit followed by a small one versus the reverse order) produce dramatically different vault balances and credit capacities, as demonstrated by the proof‑of‑concept tests. The impact is that users see their deposits disappear from the UI, vault totalDebt may become negative, and the protocol’s swap‑ratio calculations become incorrect, potentially causing users to lose funds and damaging the protocol’s reputation. The bug manifests whenever a market is created and no fee has yet been distributed, i.e., during the initial lifecycle of a vault‑market pair. It affects all participants who deposit credit before the first fee, including lenders, borrowers and any downstream swap logic that relies on accurate credit capacity. The issue was discovered during a formal audit by CodeHawks through unit‑test execution that compared state logs after different deposit orders. It is hard to notice because the contract does not revert; deposits appear to succeed, yet the on‑chain state variables remain unchanged, giving a false sense of correctness. The fix is to remove the zero‑value shortcut or to initialize the “lastVaultDistributed” values properly, ensuring that change calculations are performed regardless of prior zero values and that the early‑exit condition does not suppress legitimate updates. Conceptually, the bug belongs to the class of “incorrect zero‑initialization and guard‑clause” accounting errors that cause stale state and mismatched financial invariants.
