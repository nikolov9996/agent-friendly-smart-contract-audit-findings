---
id: 11374
severity: "High"
---

# Market-vault disconnection will bring permanent inconsistent state

## Description

In the protocol, for the most of the time, market and vault's state vars are updated by deltas, not by direct updation. This delta-change operation does not work well when market and vault connection is changed. It doesn't recognize delta by broken connection. As a result, when a vault is unlinked from a market, market's delegated credit usd will remain the same. Vault's state vars (marketRealizedDebtUsd etc) won't reflect broken connection, either.

Root Cause  
Market and vault's connection is updated by MarketMakingEngineConfigurationBranch.connectVaultAndMarkets.

The owner can add or remove vaults and markets connection by calling this external function.

After connections are updated, vaults and markets state vars will be updated by Vault.recalculateVaultsCreditCapacity. This function logic is very complicated but can be summarized as the following:  
Update weights for all credit delegations for connected markets  
Calculate deltas of realizedDebtChange, unrealizedDebtChange, usdcCreditChange, wethRewardChange between vault and connected markets  
Update vault's states by deltas calculated above  
For all connected markets, do the following:  
Calculate creditDelegation delta  
Update market's totalCreditDelegation by the above delta

While this approach works for existing connections and new one, it doesn't work well for removed connections.

Removed connections are counted out from delta calculation, so market's totalCreditDelegation won't be deducted even after a vault is disconnected.

Same thing will happen for vaults as well. i.e. Their state vars won't reflect market disconnection change.

```solidity
UD60x18 previousCreditDelegationUsdX18 = ud60x18(creditDelegation.valueUsd);

...
if (totalCreditDelegationWeightCache != 0) {
   ...
    UD60x18 newCreditDelegationUsdX18 = vaultCreditCapacityUsdX18.gt(SD59x18_ZERO)
        ? vaultCreditCapacityUsdX18.intoUD60x18().mul(creditDelegationShareX18)
        : UD60x18_ZERO;

    UD60x18 creditDeltaUsdX18 = newCreditDelegationUsdX18.sub(previousCreditDelegationUsdX18);

    Market.Data storage market = Market.load(connectedMarketId);
    market.updateTotalDelegatedCredit(creditDeltaUsdX18); // @audit creditDeltaUsdX18 does not consider removed connection
    ...
}
```

POC  
The following POC demonstrates the following scenario:  
Market 1 was connected to Vaults 1, 2  
Market's totalDelegatedCreditUsd is 1600 and creditCapacityUsd is 1680  
Market 1 is connected to Vault 1. Vault 2 has been disconnected from the market  
Recalculate market's credit deposits  
Market's updated totalDelegatedCreditUsd is still 1600 and creditCapacityUsd still remains 1680

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
    address asset = vm.addr(1);
    address usdc = vm.addr(2);
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
        vaultIds[0] = uint256(1);
        vaultIds[1] = uint256(2);
        market.id = marketId;

        LiveMarkets.Data storage liveMarkets = LiveMarkets.load();
        liveMarkets.addMarket(marketId);

        Collateral.Data storage collateral = Collateral.load(asset);
        collateral.priceAdapter = address(priceAdapter);
        collateral.creditRatio = creditRatio;

        // setup Vault 1 and Vault 2
        for (uint128 vaultId = 1; vaultId <= 2; vaultId++) {
            Vault.Data storage vault = Vault.load(vaultId);
            vault.id = vaultId;
            vault.indexToken = address(indexToken);
            vault.collateral.decimals = uint8(DEFAULT_DECIMAL);
            vault.collateral.priceAdapter = address(priceAdapter);
            vault.collateral.creditRatio = creditRatio;
        }

        // connect Market to Vault 1 and Vault 2
        uint256[] memory _vaultIds = vaultIds;
        connectVaultsAndMarkets(vaultIds);
    }

    function testInconsistencyAfterDisconnection() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();
        // deposit some values to demonstrate real-world scenario
        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100e18));

        _recalculateVaultsCreditCapacity();

        assertEq(market.getConnectedVaultsIds().length, 2);
        console.log("\nConnected Vault IDs: [1, 2]\n");
        _logMarketState();

        // Market is connected to Vault 1. 
        uint256[] memory _vaultIds = new uint256[](1);
        _vaultIds[0] = 1;
        connectVaultsAndMarkets(_vaultIds);
        market.receiveWethReward(vm.addr(3), ud60x18(0), ud60x18(1e18));
        // Vault 2 is dropped from connection
        assertEq(market.getConnectedVaultsIds().length, 1);

        _recalculateVaultsCreditCapacity();
        console.log("\nConnected Vault IDs: [1]\n");
        _logMarketState();
    }

    function connectVaultsAndMarkets(uint256[] memory vaultIds) internal {
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vm.startPrank(address(0));
        MarketMakingConfigurationBranchTest(address(this)).connectVaultsAndMarkets(marketIds, vaultIds);
        vm.stopPrank();
    }

    function _recalculateVaultsCreditCapacity() internal {
        MarketMakingConfigurationBranchTest(address(this)).updateMarketCreditDelegations(marketId);
    }

    function _logMarketState() internal {
        Market.Data storage market = Market.load(marketId);
        UD60x18 creditDepositsValueUsdX18 = market.getCreditDepositsValueUsd();
        SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();
        UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();
        SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

        emit log_named_decimal_uint("creditDepositsValueUsd", creditDepositsValueUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("marketTotalDebtUsd", marketTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("delegatedCreditUsd", delegatedCreditUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("creditCapacityUsd", creditCapacityUsdX18.unwrap(), DEFAULT_DECIMAL);
    }
}
```

Console Output

```
[PASS] testInconsistencyAfterDisconnection() (gas: 777559)
Logs:
  
Connected Vault IDs: [1, 2]

  creditDepositsValueUsd: 80.000000000000000000
  marketTotalDebtUsd: 80.000000000000000000
  delegatedCreditUsd: 1600.000000000000000000
  creditCapacityUsd: 1680.000000000000000000
  
Connected Vault IDs: [1]

  creditDepositsValueUsd: 80.000000000000000000
  marketTotalDebtUsd: 80.000000000000000000
  delegatedCreditUsd: 1600.000000000000000000
  creditCapacityUsd: 1680.000000000000000000

Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 1.80ms (838.85µs CPU time)
```

Once a vault-market connection is unlinked, the protocol will be in inconsistent state.

This inconsistency will affect usd token swap rate, vault index token swap rate and ultimately, will lead to user fund loss and protocol's reputation damage.

## Proof of Concept

The following POC demonstrates the following scenario:  
Market 1 was connected to Vaults 1, 2  
Market's totalDelegatedCreditUsd is 1600 and creditCapacityUsd is 1680  
Market 1 is connected to Vault 1. Vault 2 has been disconnected from the market  
Recalculate market's credit deposits  
Market's updated totalDelegatedCreditUsd is still 1600 and creditCapacityUsd still remains 1680

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
    address asset = vm.addr(1);
    address usdc = vm.addr(2);
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
        vaultIds[0] = uint256(1);
        vaultIds[1] = uint256(2);
        market.id = marketId;

        LiveMarkets.Data storage liveMarkets = LiveMarkets.load();
        liveMarkets.addMarket(marketId);

        Collateral.Data storage collateral = Collateral.load(asset);
        collateral.priceAdapter = address(priceAdapter);
        collateral.creditRatio = creditRatio;

        // setup Vault 1 and Vault 2
        for (uint128 vaultId = 1; vaultId <= 2; vaultId++) {
            Vault.Data storage vault = Vault.load(vaultId);
            vault.id = vaultId;
            vault.indexToken = address(indexToken);
            vault.collateral.decimals = uint8(DEFAULT_DECIMAL);
            vault.collateral.priceAdapter = address(priceAdapter);
            vault.collateral.creditRatio = creditRatio;
        }

        // connect Market to Vault 1 and Vault 2
        uint256[] memory _vaultIds = vaultIds;
        connectVaultsAndMarkets(vaultIds);
    }

    function testInconsistencyAfterDisconnection() external {
        Market.Data storage market = Market.load(marketId);

        _recalculateVaultsCreditCapacity();
        // deposit some values to demonstrate real-world scenario
        market.depositCredit(asset, ud60x18(collateralAssetAmount));
        market.settleCreditDeposit(usdc, ud60x18(100e18));

        _recalculateVaultsCreditCapacity();

        assertEq(market.getConnectedVaultsIds().length, 2);
        console.log("\nConnected Vault IDs: [1, 2]\n");
        _logMarketState();

        // Market is connected to Vault 1. 
        uint256[] memory _vaultIds = new uint256[](1);
        _vaultIds[0] = 1;
        connectVaultsAndMarkets(_vaultIds);
        market.receiveWethReward(vm.addr(3), ud60x18(0), ud60x18(1e18));
        // Vault 2 is dropped from connection
        assertEq(market.getConnectedVaultsIds().length, 1);

        _recalculateVaultsCreditCapacity();
        console.log("\nConnected Vault IDs: [1]\n");
        _logMarketState();
    }

    function connectVaultsAndMarkets(uint256[] memory vaultIds) internal {
        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = uint256(marketId);
        vm.startPrank(address(0));
        MarketMakingConfigurationBranchTest(address(this)).connectVaultsAndMarkets(marketIds, vaultIds);
        vm.stopPrank();
    }

    function _recalculateVaultsCreditCapacity() internal {
        MarketMakingConfigurationBranchTest(address(this)).updateMarketCreditDelegations(marketId);
    }

    function _logMarketState() internal {
        Market.Data storage market = Market.load(marketId);
        UD60x18 creditDepositsValueUsdX18 = market.getCreditDepositsValueUsd();
        SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();
        UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();
        SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

        emit log_named_decimal_uint("creditDepositsValueUsd", creditDepositsValueUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("marketTotalDebtUsd", marketTotalDebtUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_uint("delegatedCreditUsd", delegatedCreditUsdX18.unwrap(), DEFAULT_DECIMAL);
        emit log_named_decimal_int("creditCapacityUsd", creditCapacityUsdX18.unwrap(), DEFAULT_DECIMAL);
    }
}
```

Console Output

```
[PASS] testInconsistencyAfterDisconnection() (gas: 777559)
Logs:
  
Connected Vault IDs: [1, 2]

  creditDepositsValueUsd: 80.000000000000000000
  marketTotalDebtUsd: 80.000000000000000000
  delegatedCreditUsd: 1600.000000000000000000
  creditCapacityUsd: 1680.000000000000000000
  
Connected Vault IDs: [1]

  creditDepositsValueUsd: 80.000000000000000000
  marketTotalDebtUsd: 80.000000000000000000
  delegatedCreditUsd: 1600.000000000000000000
  creditCapacityUsd: 1680.000000000000000000

Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 1.80ms (838.85µs CPU time)
```

## Recommendation

Connection updating logic and Vault.recalculateVaultsCreditCapacity should be changed to handle disconnection scenario.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the protocol updates market and vault accounting when the relationship between a market and a vault is changed. Market‑vault connections are managed through an external function that adds or removes vaults from a market, after which a complex recalculation routine computes deltas for credit delegation, realized and unrealized debt, and reward changes. The routine only iterates over currently connected markets and vaults, calculating a credit delta based on the new delegation share. When a vault is removed, the removed connection is simply omitted from the delta loop, so no negative delta is generated. Consequently, the market’s totalDelegatedCreditUsd and the vault’s internal credit‑related state variables remain unchanged even though the vault is no longer part of the market. This creates a permanent inconsistent state where the market still reports the same delegated credit and credit capacity as before the disconnection. The inconsistency is invisible to users because the UI continues to display the same numbers, but the underlying accounting no longer reflects the true set of participants. An attacker (or any actor with permission to modify connections) can exploit this by disconnecting a vault, then performing swaps or credit‑related operations that rely on the stale credit capacity. Because the market believes it has more delegated credit than it actually does, it may offer overly favorable swap rates, leading to under‑collateralisation and potential loss of user funds. The impact spreads to any user interacting with the affected market, to vault owners whose balances are no longer correctly accounted for, and to the protocol’s reputation and overall solvency. The issue was discovered during a security audit when a test case showed that after removing a vault and invoking the recalculation function, the market’s delegatedCreditUsd and creditCapacityUsd values remained identical to the pre‑removal state. The bug is hard to notice because no transaction reverts, no events indicate an error, and the numbers printed in logs appear unchanged. To remediate the problem, the connection‑updating logic and the Vault.recalculateVaultsCreditCapacity routine must be extended to explicitly handle disconnections: they should compute a negative credit delta for each removed vault, update the market’s totalDelegatedCreditUsd accordingly, and adjust all vault‑side state variables so that they accurately reflect the current set of connections. This ensures that credit capacity calculations remain consistent with the actual market‑vault topology and prevents the protocol from operating on stale accounting data.
