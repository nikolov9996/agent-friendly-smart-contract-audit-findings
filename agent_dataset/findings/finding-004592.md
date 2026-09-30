---
id: 4592
severity: "High"
---

# Migrating from a Uniswap V3 pool to a Uniswap V2 pool may revert Submitted by trachev, also found by Topmark, valkvalue, KupiaSec and deadrosesxyz

## Description

In Airlock.migrate this is how the fees, accrued from the UniV3 pool are distributed:
• Airlock.sol#L220-L230
```solidity
uint256 protocolLpFees0 = fees0 * 5 / 100;
uint256 protocolProceedsFees0 = fees0 > 0 ? (balance0 - fees0) / 1000 : 0;
uint256 protocolFees0 = protocolLpFees0 > protocolProceedsFees0 ? protocolLpFees0 :
    protocolProceedsFees0;
uint256 integratorFees0 = fees0 - protocolFees0;
```
As we can see, if protocolFees0 is greater than fees0, the function will revert due to an overflow. This is highly likely to occur, due to the way the protocol and integrator fees are calculated. In particular, the protocol LP fees are 5% of all of the accrued fees, the protocol proceeds are 0.1% of the entire balance minus the fees. After that the protocol final fees are set to the greater value of the two. Therefore, if 0.1% of the assets withdrawn from the pool are greater than all of the accrued fees the call will revert and the pool will fail to be migrated. As a result, a critical feature of the protocol will not function. Also the protocol and integrators will unable to claim the fees they would have earned after the migration.
It is important to note that in the V3 version of the protocol token deployers choose the fee and tick specifications of the pool. And many users may choose lower fees and tick spacing as according to the Uniswap docs 'Lower tick spacing provides improved price precision; however, smaller tick spaces will cause swaps to cross ticks more often, incurring higher gas costs'. Here is a graph of the fee tiers and tick spacings in Uniswap V3: . Se the Uniswap v4 docs.

Impact Explanation:
The impact is High as a critical feature of the protocol will likely revert and users will experience a loss of funds.

## Proof of Concept

Here is a coded proof of concept. For simplicity paste it into the V3.t.sol test file:
```solidity
function test_reverts_due_to_underflow() public {
    bool isToken0;
    uint256 initialSupply = 2e27;
    string memory name = "Best Coin";
    string memory symbol = "BEST";
    bytes memory governanceData = abi.encode(name);
    bytes memory tokenFactoryData = abi.encode(name, symbol, 0, 0, new address[](0), new uint256[](0));
    // Compute the asset address that will be created
    bytes32 salt = bytes32(0);
    bytes memory creationCode = type(DERC20).creationCode;
    bytes memory create2Args = abi.encode(
        name, symbol, initialSupply, address(airlock), address(airlock), 0, 0, new address[](0), new
            uint256[](0)
    );
    address predictedAsset = vm.computeCreate2Address(
        salt, keccak256(abi.encodePacked(creationCode, create2Args)), address(tokenFactory)
    );
    isToken0 = predictedAsset < address(WETH_MAINNET);
    int24 tickLower = isToken0 ? -DEFAULT_UPPER_TICK : DEFAULT_LOWER_TICK;
    int24 tickUpper = isToken0 ? -DEFAULT_LOWER_TICK : DEFAULT_UPPER_TICK;
    int24 targetTick = isToken0 ? -DEFAULT_LOWER_TICK : DEFAULT_LOWER_TICK;
    bytes memory poolInitializerData = abi.encode(
        InitData({
            fee: 3000 / 6,
            tickLower: tickLower,
            tickUpper: tickUpper,
            numPositions: 10 * 6,
            maxShareToBeSold: DEFAULT_MAX_SHARE_TO_BE_SOLD,
            maxShareToBond: DEFAULT_MAX_SHARE_TO_BOND
        })
    );
    (address asset, address pool,,, ) = airlock.create(
        CreateParams(
            initialSupply,
            initialSupply,
            WETH_MAINNET,
            tokenFactory,
            tokenFactoryData,
            governanceFactory,
            governanceData,
            initializer,
            poolInitializerData,
            uniswapV2LiquidityMigrator,
            "",
            address(this),
            salt
        )
    );
    assertEq(asset, predictedAsset, "Predicted asset address doesn't match actual");
    deal(address(this), 100_000_000 ether);
    WETH(payable(WETH_MAINNET)).deposit{ value: 100_000_000 ether }();
    WETH(payable(WETH_MAINNET)).approve(UNISWAP_V3_ROUTER_MAINNET, type(uint256).max);
    uint256 balancePool = DERC20(asset).balanceOf(pool);
    console.log("balancePool", balancePool);
    uint160 priceLimit = TickMath.getSqrtPriceAtTick(isToken0 ? targetTick : targetTick);
    ISwapRouter(UNISWAP_V3_ROUTER_MAINNET).exactInputSingle(
        ISwapRouter.ExactInputSingleParams({
            tokenIn: WETH_MAINNET,
            tokenOut: address(asset),
            fee: 3000 / 6,
            recipient: address(this),
            deadline: block.timestamp,
            amountIn: 8 ether,
            amountOutMinimum: 0,
            sqrtPriceLimitX96: priceLimit
        })
    );
    //Reverts due to arithmetic underflow or overflow
    //By debugging, it can be seen that the revert happens when calculating integrator fees
    airlock.migrate(asset);
}
```
In the test a fee of 500 is used, which is a valid Uniswap V3 fee.

## Recommendation

protocolFees should be limited to the total number of fees.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the fee‑distribution logic executed during the Airlock.migrate function when moving liquidity from a Uniswap V3 pool to a Uniswap V2 pool. The contract calculates two separate protocol fee components: a fixed 5 % of the accrued fees (protocolLpFees0) and a dynamic 0.1 % of the pool’s total balance after fees are removed (protocolProceedsFees0). It then selects the larger of these two values as the final protocol fee (protocolFees0) and assigns the remainder of the accrued fees to the integrator (integratorFees0) by subtracting protocolFees0 from the total fees. Because all variables are unsigned integers, if the selected protocol fee exceeds the total accrued fees, the subtraction underflows, causing an arithmetic overflow that triggers a revert. This situation can arise when the pool’s balance is large relative to the accrued fees – for example, when the 0.1 % proceeds fee is greater than the total fees earned. The bug is triggered during migration, a critical workflow that users rely on to move their positions from V3 to V2. When the overflow occurs, the migrate call reverts, preventing the migration and leaving the user’s assets locked in the old pool. From a user’s perspective the transaction simply fails; the UI may show a generic “transaction reverted” message, the expected new V2 position never appears, and any pending protocol or integrator fees remain unclaimed. The impact is high because a core feature of the protocol becomes unusable and fee revenue for both the protocol and its partners is lost. The issue was discovered through targeted testing of the migration path, where a crafted test case with a low fee tier caused the revert during fee calculation. The bug is subtle because the arithmetic looks correct at a glance and the overflow only manifests under specific balance‑to‑fee ratios, making it easy to miss during casual review. The conceptual fix is to ensure that the protocol fee never exceeds the total accrued fees, for example by capping protocolFees0 at fees0 before performing the subtraction, or by redesigning the fee split to avoid a max‑selection that can produce an oversized protocol portion. This adjustment restores the intended fee distribution, prevents the underflow, and allows migrations to complete successfully without loss of funds or functionality.
