---
id: 22627
severity: "High"
---

# Claiming rebasing token rewards in ReserveL-

## Description

The code added to ReserveLogic.sol::_updateIndexes in order to claim rebasing interest, uses address(this) instead of the Atoken address for getClaimableAmount and calls claim directly instead of through the Atoken, both of which are wrong and will cause the function to fail.
The following code snippet was added to ReserveLogic.sol::_updateIndexes with the intention of claiming any rebasing interest accrued in rebasing underlying tokens, and add it to the relevant AToken as additional LP profit:
```solidity
// claimableAmount always has 18 decimals, since both USDB and WETH have 18 decimals
uint256 claimableAmount = (underlyingAsset == USDB || underlyingAsset == WETH)
    ? IERC20Rebasing(underlyingAsset).getClaimableAmount(address(this))
    : 0;
// only accrue native yield if there is something to be claimed
if (claimableAmount > 0) {
    uint256 totalPoolHoldings = IERC20(underlyingAsset).balanceOf(aTokenAddress)
        + // pool liquidity
        IERC20(reserve.stableDebtTokenAddress).totalSupply() // total stable debt
        + IERC20(reserve.variableDebtTokenAddress).totalSupply(); // total variable debt
    // express claimable amount as a percentage of pool assets and convert from wad to ray
    uint256 claimedInterestIndex =
        claimableAmount.wadDiv(totalPoolHoldings).wadToRay();
    // update pool liquidity index to reflect accrued native
    newLiquidityIndex = claimedInterestIndex.rayMul(newLiquidityIndex);
    reserve.liquidityIndex = uint128(newLiquidityIndex);
    require(newLiquidityIndex <= type(uint128).max,
        Errors.RL_LIQUIDITY_INDEX_OVERFLOW);
    // claim and send yield to the aToken
    IERC20Rebasing(underlyingAsset).claim(address(aTokenAddress),
        claimableAmount);
}
```
The root cause of the issue is that the code uses address(this) (the LendingPool in this context) instead of the AToken address which is the real owner of the rebalancing token liquidity. This happens in two places:
1. The getClaimableAmount function is called with address(this) (the LendingPool address in this context) instead of the AToken which is the real owner of the underlying asset (and that is configured as CLAIMABLE). On mainnet the function would fail because getClaimableAmount fails when called on an account that is not configured as CLAIMABLE (which is the case for the LendingPool address) as seen here (from the WETH ERC20Rebasing source code on the Blast mainnet explorer):
```solidity
function getClaimableAmount(address account) public view returns (uint256) {
    if (getConfiguration(account) != YieldMode.CLAIMABLE) {
        revert NotClaimableAccount();
    }
    uint256 shareValue = _computeShareValue(sharePrice(), _shares[account],
        _remainders[account]);
}
```
2. The function calls the rebasing token's claim function directly (with LendingPool as the msg.sender), with the AToken address as the recipient, again wrongfully because the LendingPool contract doesn't hold the underlying balance (the AToken does).
WETH and USDB addresses are wrongfully configured in ReserveLogic (supposedly to sepolia addresses but there is an error in the addresses):
```solidity
address constant USDB = 0x4300000000000000000000000000000000000022;
address constant WETH = 0x4300000000000000000000000000000000000023;
```
Compare with the correct sepolia addresses as configured in the AToken.sol contract:
```solidity
IERC20Rebasing public constant USDB =
    IERC20Rebasing(0x4200000000000000000000000000000000000022);
IERC20Rebasing public constant WETH =
    IERC20Rebasing(0x4200000000000000000000000000000000000023);
```
The POC below shows how, if the addresses are corrected in ReserveLogic, the function fails with a call that requires a status update on a rebalancing reserve token.
This error would cause the function to fail whenever is it called for a reserve with a rebasing underlying token, because of the call to getClaimableAmount with an account that is not configured as YieldMode.CLAIMABLE. If the LendingPool token is configured to YieldMode.CLAIMABLE the function doesn't fail but no claimable amounts are attributed to LPs because the wrong account is being checked.

## Proof of Concept

how to run
(The first three steps can be done once and apply to all my POCs in this contest)
1. Run forge init in a new folder
2. Run forge install openzeppelin/openzeppelin-contracts@v3.1.0 --no-commit
3. Copy everything under seismic-protocol-v2\contracts to the src folder
4. Create a test.sol file under the test folder and copy the code below to it.
5. Run forge test --match-test testClaimProblemPOC --fork-url https://sepolia.blast.io -vvv
6. change token addresses in ReserveLogic.sol line 30 to:
```solidity
//address constant USDB = 0x4200000000000000000000000000000000000022;
//address constant WETH = 0x4200000000000000000000000000000000000023;
```
5. Run forge test --match-test testClaimProblemPOC --fork-url https://sepolia.blast.io -vvv again to see the revert.
Test.sol Code:
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;
import {Test, console2} from "forge-std/Test.sol";
import {IERC20} from '../src/dependencies/openzeppelin/contracts/IERC20.sol';
import {IERC20Detailed} from '../src/dependencies/openzeppelin/contracts/IERC20Detailed.sol';
import {LendingPool} from "../src/protocol/lendingpool/LendingPool.sol";
import {ILendingPoolAddressesProvider} from "../src/interfaces/ILendingPoolAddressesProvider.sol";
import {ILendingRateOracle} from "../src/interfaces/ILendingRateOracle.sol";
import {IPriceOracleGetter} from "../src/interfaces/IPriceOracleGetter.sol";
import {LendingPoolConfigurator} from "../src/protocol/lendingpool/LendingPoolConfigurator.sol";
import "../src/protocol/libraries/types/DataTypes.sol";
import {LendingPoolCollateralManager} from "../src/protocol/lendingpool/LendingPoolCollateralManager.sol";
import {LendingPoolAddressesProvider} from "../src/protocol/configuration/LendingPoolAddressesProvider.sol";
import {AaveProtocolDataProvider} from "../src/misc/AaveProtocolDataProvider.sol";
import {AaveOracle} from "../src/misc/AaveOracle.sol";
import {IERC20Rebasing, YieldMode} from '../src/misc/interfaces/IERC20Rebasing.sol';
import {IBlastPoints} from '../src/misc/interfaces/IBlastPoints.sol';
import {IWETH} from '../src/misc/interfaces/IWETH.sol';
import {ILendingPoolConfigurator} from "../src/interfaces/ILendingPoolConfigurator.sol";
import {AToken} from "../src/protocol/tokenization/AToken.sol";
import {StableDebtToken} from "../src/protocol/tokenization/StableDebtToken.sol";
import {VariableDebtToken} from "../src/protocol/tokenization/VariableDebtToken.sol";
import {DefaultReserveInterestRateStrategy} from "../src/protocol/lendingpool/DefaultReserveInterestRateStrategy.sol";
import {LendingRateOracle} from "../src/mocks/oracle/LendingRateOracle.sol";

contract AaveTest is Test {
    address public user = makeAddr("user");
    address public user1 = makeAddr("user1");
    address public pool_admin = makeAddr("poolAdmin");
    address public pool_emerg_admin = makeAddr("pool_emerg_admin");
    address public treasury_usdb = makeAddr("treasury_usdb");
    address public treasury_weth = makeAddr("treasury_weth");
    address public PYTH_CONTRACT = 0xA2aa501b19aff244D90cc15a4Cf739D2725B5729;
    bytes32 PYTH_USDB_FEED_ID = 0x433faaa801ecdb6618e3897177a118b273a8e18cc3ff545aadfc207d58d028f7;
    address POINTS_OPERATOR = 0xc783df8a850f42e7F7e57013759C285caa701eB6;
    address public usdb_holder = 0x3df9C3E7105B2bEdd0b7b75c9ECF5C9041313186;
    IERC20Rebasing public USDB = IERC20Rebasing(0x4200000000000000000000000000000000000022);
    IERC20Rebasing public WETH = IERC20Rebasing(0x4200000000000000000000000000000000000023);
    string public marketId = "testMarket";
    LendingPool public lending_pool;
    LendingPoolAddressesProvider public address_provider;
    LendingPoolConfigurator public pool_configurator;
    LendingPoolCollateralManager public pool_collateral_manager;
    AaveOracle public price_oracle;
    ILendingRateOracle public lendingRateOracle;
    AaveProtocolDataProvider public aave_protocol_data_provider;
    DefaultReserveInterestRateStrategy public defualt_strategy;

    function setUp() public virtual {
        address_provider = new LendingPoolAddressesProvider(marketId);
        //init lending pool
        LendingPool lending_pool_impl = new LendingPool();
        address_provider.setLendingPoolImpl(address(lending_pool_impl));
        lending_pool = LendingPool(address_provider.getLendingPool());
        //init lending pool configurator
        LendingPoolConfigurator pool_configurator_impl = new LendingPoolConfigurator();
        address_provider.setLendingPoolConfiguratorImpl(address(pool_configurator_impl));
        pool_configurator = LendingPoolConfigurator(address_provider.getLendingPoolConfigurator());
        //init LendingPoolCollateralManager
        LendingPoolCollateralManager pool_collateral_mamager_impl = new LendingPoolCollateralManager();
        address_provider.setLendingPoolCollateralManager(address(pool_collateral_mamager_impl));
        pool_collateral_manager = LendingPoolCollateralManager(address_provider.getLendingPoolCollateralManager());
        //init Pool Oracle
        address[] memory assets = new address[](1);
        assets[0] = address(USDB);
        bytes32[] memory feedids = new bytes32[](1);
        feedids[0] = PYTH_USDB_FEED_ID;
        price_oracle = new AaveOracle(PYTH_CONTRACT, assets, feedids);
        address_provider.setPriceOracle(address(price_oracle));
        //init lendingRateOracle
        lendingRateOracle = new LendingRateOracle();
        address_provider.setLendingRateOracle(address(lendingRateOracle));
        lendingRateOracle.setMarketBorrowRate(address(WETH), 0.02*1e27);
        lendingRateOracle.setMarketBorrowRate(address(USDB), 0.02*1e27);
        address_provider.setPoolAdmin(pool_admin);
        address_provider.setEmergencyAdmin(pool_emerg_admin);
        address_provider.setMarketId(marketId);
        //init data provider
        aave_protocol_data_provider = new AaveProtocolDataProvider(ILendingPoolAddressesProvider(address_provider));
        defualt_strategy = new DefaultReserveInterestRateStrategy(address_provider,
            0.725*1e27,
            0.02*1e27,
            0.05*1e27,
            0.9*1e27,
            0.07*1e27,
            0.9*1e27
        );
        //add tokens as reserves
        InitToken(address(USDB), treasury_usdb,
            address(defualt_strategy),
            "aave USDB",
            "aUSDB",
            "aave USDB Var",
            "aUSDBVar",
            "aave USDB Stable",
            "aUSDBSta");
        InitToken(address(WETH), treasury_weth,
            address(defualt_strategy),
            "aave WETH",
            "aWETH",
            "aave WETH Var",
            "aWETHVar",
            "aave WETH Stable",
            "aWETHSta");
    }

    function testClaimProblemPOC() public {
        //deposit some WETH to the pool
        vm.startPrank(user);
        deal(user, 100e18);
        IWETH(address(WETH)).deposit{value: 100e18}();
        IERC20(address(WETH)).approve(address(lending_pool), 100e18);
        lending_pool.deposit(address(WETH), 5e18, user, 0);
        (address aWeth,,) = aave_protocol_data_provider.getReserveTokensAddresses(address(WETH));
        printRebalancingBals("AToken Weth balance and claimable at start:", WETH, aWeth);
        //OUTPUT
        //Balance 5000000000000000000
        //Claimable: 0
        //workaround to simulate 10% accrued interest to WETH holders (since warping time won't do it)
        deal(address(WETH), address(WETH).balance * 110 / 100);
        printRebalancingBals("AToken Weth balance and claimable after interest accrual", WETH, aWeth);
        //OUTPUT
        //Balance 5000000000000000000
        //Claimable: 613881253978048657
        //another small deposit to trigger a call to _updateIndexes where the claiming code is
        //address constant USDB = 0x4200000000000000000000000000000000000022;
        //address constant WETH = 0x4200000000000000000000000000000000000023;
        //this call reverts because getClaimableAmount is called with LendingPool which is not configured as CLAIMABLE
        lending_pool.deposit(address(WETH), 0.00000001e18, user, 0);
        printRebalancingBals("AToken Weth balance and claimable after pool claiming:", WETH, aWeth);
        //OUTPUT
        //Balance 5000000010000000000
        //Claimable: 613880470540939226
        vm.stopPrank();
    }

    //prints the current balance and claimable amounts of the given address
    function printRebalancingBals(string memory message, IERC20Rebasing token, address user) public {
        console2.log(message);
        console2.log("Balance %s", IERC20(address(token)).balanceOf(user));
        console2.log("Claimable: %s\n", token.getClaimableAmount(user));
    }

    function InitToken(
        address underlying,
        address treasury,
        address strategy,
        string memory atokenName,
        string memory atokenSymbol,
        string memory vatTname,
        string memory varTSymbol,
        string memory stableTname,
        string memory stableTsymbol
    ) public {
        vm.startPrank(pool_admin);
        ILendingPoolConfigurator.InitReserveInput[] memory input = new ILendingPoolConfigurator.InitReserveInput[](1);
        input[0].aTokenImpl = address(new AToken());
        input[0].stableDebtTokenImpl = address(new StableDebtToken());
        input[0].variableDebtTokenImpl = address(new VariableDebtToken());
        input[0].underlyingAssetDecimals = 18;
        input[0].interestRateStrategyAddress = strategy;
        input[0].underlyingAsset = underlying;
        input[0].treasury = treasury;
        input[0].incentivesController = address(0);
        input[0].underlyingAssetName = "Rebasing USD";
        input[0].aTokenName = atokenName;
        input[0].aTokenSymbol = atokenSymbol;
        input[0].variableDebtTokenName = vatTname;
        input[0].variableDebtTokenSymbol = varTSymbol;
        input[0].stableDebtTokenName = stableTname;
        input[0].stableDebtTokenSymbol = stableTsymbol;
        input[0].pointsOperator = POINTS_OPERATOR;
        input[0].params = "";
        pool_configurator.batchInitReserve(input);
        pool_configurator.activateReserve(underlying);
        pool_configurator.enableBorrowingOnReserve(underlying, true);
        pool_configurator.configureReserveAsCollateral(underlying, 8000, 8250, 10500);
        pool_configurator.setReserveFactor(underlying, 1000);
        vm.stopPrank();
    }
}
```

## Recommendation

1. The first issue is easily fixable by calling getClaimableAmount with the relevant AToken address instead of address(this).
LendingPool, that claims the entire claimable amount to the AToken. (since only the AToken can call claim on its own balance).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the ReserveLogic::_updateIndexes routine that attempts to claim rebasing token rewards for a reserve that holds a rebasing underlying asset such as USDB or WETH. The implementation mistakenly queries the rebasing token’s getClaimableAmount function with address(this), which in this context is the LendingPool contract, instead of the AToken address that actually owns the underlying balance. Because the rebasing token only permits accounts configured with YieldMode.CLAIMABLE to query claimable amounts, the call reverts with NotClaimableAccount when the LendingPool address is used. A second mistake is that the code calls the rebasing token’s claim function directly from the LendingPool, passing the AToken address as the recipient. The LendingPool does not hold the underlying balance, so the claim cannot be executed even if the first call succeeded. In addition, the constant addresses for USDB and WETH are hard‑coded to the wrong network values, further preventing correct identification of the rebasing tokens. When a reserve with a rebasing underlying token triggers _updateIndexes – for example during a deposit, withdrawal, or any operation that updates liquidity indexes – the erroneous calls cause the entire transaction to revert. As a result, liquidity providers do not receive the additional rebasing rewards that should be accrued to the AToken, breaking the accounting model that expects these rewards to be added to the pool’s liquidity index. Users see symptoms such as a zero claimable amount, missing balance updates, or a transaction that fails unexpectedly after a small deposit. The issue was discovered during a manual audit and reproduced with a Forge test that deliberately corrected the token addresses and observed a revert when the pool attempted to claim rewards. The bug is subtle because the code compiles and the logic appears correct at a glance; the failure only manifests for specific rebasing assets and only when the internal claim path is exercised. To remediate, the getClaimableAmount call must be made with the AToken address, the claim function should be invoked by the AToken itself (or via a proper internal call that respects the token’s ownership model), and the constant addresses for the rebasing tokens must be updated to the correct network values. This fixes the claim flow, restores proper reward accrual, and aligns the protocol’s accounting with its business logic that LPs earn rebasing interest.
