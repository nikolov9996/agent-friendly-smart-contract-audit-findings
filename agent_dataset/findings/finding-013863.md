---
id: 13863
severity: "High"
---

# Slight miscalculation in maxAmountsIn for Admin Fee Logic in UpliftOnlyExample::onAfterRemoveLiquidity Causes Lock of All Funds

## Description

The function onAfterRemoveLiquidity is responsible for handling post-liquidity removal operations, including fee calculations and administering liquidity back to the pool or QuantAMMAdmin. However, there is a subtle miscalculation in the maxAmountsIn parameter in line 541 during admin fee processing, particularly when localData.adminFeePercent > 0

When the admin fee is calculated and accrued fees are intended to be added back to the liquidity pool, the value of maxAmountsIn becomes slightly less than the actual token amounts required. This leads to a mismatch during the addLiquidity operation in the _vault, which results in a reversion with the following error:

```solidity
AmountInAboveMax(token, amountInRaw, params.maxAmountsIn[i])
```

This issue prevents liquidity removal operations from completing successfully, effectively locking user funds in the pool.

The problem lies in the following block of code:

```solidity
        if (localData.adminFeePercent > 0) {
            _vault.addLiquidity(
                AddLiquidityParams({
                    pool: localData.pool,
                    to: IUpdateWeightRunner(_updateWeightRunner).getQuantAMMAdmin(),
                    maxAmountsIn: localData.accruedQuantAMMFees,
                    minBptAmountOut: localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18,
                    kind: AddLiquidityKind.PROPORTIONAL,
                    userData: bytes("")
                })
            );
            emit ExitFeeCharged(
                userAddress,
                localData.pool,
                IERC20(localData.pool),
                localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18
            );
        }
```

Here:
localData.accruedQuantAMMFees[i] is calculated using:

```solidity
localData.accruedQuantAMMFees[i] = exitFee.mulDown(localData.adminFeePercent);
```

However, as vault calculation favours the vault over the user, the calculated amountInRaw in vault is slightly more than the params.maxAmountsIn[i]. Ref-[1
When the _vault validates the input via:

```solidity
if (amountInRaw > params.maxAmountsIn[i]) {
    revert AmountInAboveMax(token, amountInRaw, params.maxAmountsIn[i]);
}
```

The slight discrepancy causes a reversion, even when the difference is only by 1 wei.

All liquidity removal operations revert, effectively locking user funds in the pool.

## Proof of Concept

Create a new file named UpLiftHookTest.t.sol in pkg/pool-hooks/test/foundry/
Paste the following code:

```solidity
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
pragma solidity ^0.8.24;

import { BaseVaultTest } from "@balancer-labs/v3-vault/test/foundry/utils/BaseVaultTest.sol";
import { QuantAMMWeightedPool, IQuantAMMWeightedPool } from "pool-quantamm/contracts/QuantAMMWeightedPool.sol";
import {QuantAMMWeightedPoolFactory} from "pool-quantamm/contracts/QuantAMMWeightedPoolFactory.sol";
import { UpdateWeightRunner, IUpdateRule } from "pool-quantamm/contracts/UpdateWeightRunner.sol";
import { MockChainlinkOracle } from "./utils/MockOracle.sol";
import "@balancer-labs/v3-interfaces/contracts/pool-quantamm/OracleWrapper.sol";
import { IUpdateRule } from "pool-quantamm/contracts/rules/UpdateRule.sol";
import { MockMomentumRule } from "pool-quantamm/contracts/mock/mockRules/MockMomentumRule.sol";
import { UpliftOnlyExample } from "../../contracts/hooks-quantamm/UpliftOnlyExample.sol";
import { IPermit2 } from "permit2/src/interfaces/IPermit2.sol";
import { IVault } from "@balancer-labs/v3-interfaces/contracts/vault/IVault.sol";
import { IVaultAdmin } from "@balancer-labs/v3-interfaces/contracts/vault/IVaultAdmin.sol";
import { PoolRoleAccounts, TokenConfig, HooksConfig } from "@balancer-labs/v3-interfaces/contracts/vault/VaultTypes.sol";
import { IWETH } from "@balancer-labs/v3-interfaces/contracts/solidity-utils/misc/IWETH.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { Router } from "@balancer-labs/v3-vault/contracts/Router.sol";
import {console} from "forge-std/console.sol";

contract UpLiftHookTest is BaseVaultTest {  // use default dai, usdc, weth and mock oracle
    //address daiOnETH = 0x6B175474E89094C44Da98b954EedeAC495271d0F;
    //address usdcOnETH = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    //address wethOnETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    uint256 internal daiIdx;
    uint256 internal usdcIdx;

    uint256 SWAPFEEPERCENTAGE = 10e16;

    address quantAdmin = makeAddr("quantAdmin");
    address owner = makeAddr("owner");
    address poolCreator = makeAddr("poolCreator");
    address liquidityProvider1 = makeAddr("liquidityProvider1");
    address liquidityProvider2 = makeAddr("liquidityProvider2");
    address attacker = makeAddr("attacker");
    //address usdcUsd = 0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6;
    //address daiUsd = 0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9;
    //address ethOracle = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;

    QuantAMMWeightedPool public weightedPool;
    QuantAMMWeightedPoolFactory public weightedPoolFactory;
    UpdateWeightRunner public updateWeightRunner;
    MockChainlinkOracle mockOracledai;
    MockChainlinkOracle mockOracleusdc;
    MockChainlinkOracle ethOracle;
    Router externalRouter;

    UpliftOnlyExample upLifthook;

    function setUp() public override {
        vm.warp(block.timestamp + 3600);
        mockOracledai = new MockChainlinkOracle(1e18, 0);
        mockOracleusdc = new MockChainlinkOracle(1e18, 0);
        ethOracle = new MockChainlinkOracle(2000e18, 0);
        updateWeightRunner = new UpdateWeightRunner(quantAdmin, address(ethOracle));

        vm.startPrank(quantAdmin);
        updateWeightRunner.addOracle(OracleWrapper(address(mockOracledai)));
        updateWeightRunner.addOracle(OracleWrapper(address(mockOracleusdc)));
        vm.stopPrank();

        super.setUp();

        (daiIdx, usdcIdx) = getSortedIndexes(address(dai), address(usdc));

        vm.prank(quantAdmin);
        updateWeightRunner.setApprovedActionsForPool(pool, 2);
    }

    function createHook() internal override returns (address) {
        // Create the factory here, because it needs to be deployed after the Vault, but before the hook contract.
        weightedPoolFactory = new QuantAMMWeightedPoolFactory(IVault(address(vault)), 365 days, "Factory v1", "Pool v1", address(updateWeightRunner));
        // lp will be the owner of the hook. Only LP is able to set hook fee percentages.
        vm.prank(quantAdmin);
        upLifthook = new UpliftOnlyExample(IVault(address(vault)), IWETH(weth), IPermit2(permit2), 100, 100, address(updateWeightRunner), "version 1", "lpnft", "LP-NFT");
        return address(upLifthook);
    }

    function _createPool(
        address[] memory tokens,
        string memory label
    ) internal override returns (address newPool, bytes memory poolArgs) {
        QuantAMMWeightedPoolFactory.NewPoolParams memory poolParams = _createPoolParams(tokens);

        (newPool, poolArgs) = weightedPoolFactory.create(poolParams);
        vm.label(newPool, label);

        authorizer.grantRole(vault.getActionId(IVaultAdmin.setStaticSwapFeePercentage.selector), quantAdmin);
        vm.prank(quantAdmin);
        vault.setStaticSwapFeePercentage(newPool, SWAPFEEPERCENTAGE);
    }

    function _createPoolParams(address[] memory tokens) internal returns (QuantAMMWeightedPoolFactory.NewPoolParams memory retParams) {
        PoolRoleAccounts memory roleAccounts;

        uint64[] memory lambdas = new uint64[]();
        lambdas[0] = 0.2e18;
        
        int256[][] memory parameters = new int256[][]();
        parameters[0] = new int256[]();
        parameters[0][0] = 0.2e18;

        address[][] memory oracles = new address[][]();
        oracles[0] = new address[]();
        oracles[0][0] = address(mockOracledai);
        oracles[1] = new address[]();
        oracles[1][0] = address(mockOracleusdc);

        uint256[] memory normalizedWeights = new uint256[]();
        normalizedWeights[0] = uint256(0.5e18);
        normalizedWeights[1] = uint256(0.5e18);

        IERC20[] memory ierctokens = new IERC20[]();
        for (uint256 i = 0; i < tokens.length; i++) {
            ierctokens[i] = IERC20(tokens[i]);
        }

        int256[] memory initialWeights = new int256[]();
        initialWeights[0] = 0.5e18;
        initialWeights[1] = 0.5e18;
        
        int256[] memory initialMovingAverages = new int256[]();
        initialMovingAverages[0] = 0.5e18;
        initialMovingAverages[1] = 0.5e18;
        
        int256[] memory initialIntermediateValues = new int256[]();
        initialIntermediateValues[0] = 0.5e18;
        initialIntermediateValues[1] = 0.5e18;
        
        TokenConfig[] memory tokenConfig = vault.buildTokenConfig(ierctokens);
        
        retParams = QuantAMMWeightedPoolFactory.NewPoolParams(
            "Pool With Donation",
            "PwD",
            tokenConfig,
            normalizedWeights,
            roleAccounts,
            0.02e18,
            address(poolHooksContract),
            true,
            true, // Do not disable unbalanced add/remove liquidity
            0x0000000000000000000000000000000000000000000000000000000000000000,
            initialWeights,
            IQuantAMMWeightedPool.PoolSettings(
                ierctokens,
                IUpdateRule(new MockMomentumRule(owner)),
                oracles,
                60,
                lambdas,
                0.2e18,
                0.2e18,
                0.3e18,
                parameters,
                poolCreator
            ),
            initialMovingAverages,
            initialIntermediateValues,
            3600,
            16,//able to set weights
            new string[][]()
        );
    }

    function testRemoveLiquidityUplift() public {
        addLiquidity();
        
        uint256[] memory minAmountsOut = new uint256[]();
        minAmountsOut[0] = 1;
        minAmountsOut[1] = 1;

        vm.prank(liquidityProvider1);
        UpliftOnlyExample(payable(poolHooksContract)).removeLiquidityProportional(2e18, minAmountsOut, true, pool);
    }

    function addLiquidity() public {
        deal(address(dai), liquidityProvider1, 100e18);
        deal(address(usdc), liquidityProvider1, 100e18);

        uint256[] memory maxAmountsIn = new uint256[]();
        maxAmountsIn[0] = 2.1e18;
        maxAmountsIn[1] = 2.1e18;
        uint256 exactBptAmountOut = 2e18;

        vm.startPrank(liquidityProvider1);
        IERC20(address(dai)).approve(address(permit2), 100e18);
        IERC20(address(usdc)).approve(address(permit2), 100e18);
        permit2.approve(address(dai), address(poolHooksContract), 100e18, uint48(block.timestamp));
        permit2.approve(address(usdc), address(poolHooksContract), 100e18, uint48(block.timestamp));
        UpliftOnlyExample(payable(poolHooksContract)).addLiquidityProportional(pool, maxAmountsIn, exactBptAmountOut, false, abi.encodePacked(liquidityProvider1));
        vm.stopPrank();

        deal(address(dai), liquidityProvider2, 100e18);
        deal(address(usdc), liquidityProvider2, 100e18);

        vm.startPrank(liquidityProvider2);
        IERC20(address(dai)).approve(address(permit2), 100e18);
        IERC20(address(usdc)).approve(address(permit2), 100e18);
        permit2.approve(address(dai), address(poolHooksContract), 100e18, uint48(block.timestamp));
        permit2.approve(address(usdc), address(poolHooksContract), 100e18, uint48(block.timestamp));
        UpliftOnlyExample(payable(poolHooksContract)).addLiquidityProportional(pool, maxAmountsIn, exactBptAmountOut, false, abi.encodePacked(liquidityProvider2));
        vm.stopPrank();

        console.log("Liquidity added");
    }
```
Go the the pool-hooks folder using terminal and run forge test --mt testRemoveLiquidityUplift -vv
The test will revert with error:

```solidity
AmountInAboveMax()
```

## Recommendation

Add a small buffer to localData.accruedQuantAMMFees to account for precision errors. For example:

```solidity
for(uint256 i=0; i<localData.accruedQuantAMMFees.length; i++) {
    localData.accruedQuantAMMFees[i] += 1;
    hookAdjustedAmountsOutRaw[i] -= 1;
}
```
Or reduce the minBptAmountOut slightly:

```diff
        if (localData.adminFeePercent > 0) {
            _vault.addLiquidity(
                AddLiquidityParams({
                    pool: localData.pool,
                    to: IUpdateWeightRunner(_updateWeightRunner).getQuantAMMAdmin(),
                    maxAmountsIn: localData.accruedQuantAMMFees,
minBptAmountOut: localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18,
minBptAmountOut: localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18 -1,
                    kind: AddLiquidityKind.PROPORTIONAL,
                    userData: bytes("")
                })
            );
            emit ExitFeeCharged(
                userAddress,
                localData.pool,
                IERC20(localData.pool),
                localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18
            );
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a subtle rounding error that occurs in the post‑liquidity‑removal hook when an admin fee is configured. After a user initiates a proportional removal, the hook calculates the amount of fee tokens that must be sent back to the pool (accruedQuantAMMFees) by multiplying the exit fee with the admin fee percentage using a down‑rounding multiplication. This value is then passed to the vault as maxAmountsIn, which represents the maximum token amount the vault is allowed to accept. The vault, however, performs its own internal calculation of the exact amount required (amountInRaw) and, because its arithmetic favours the vault, the result is often a tiny amount larger than the supplied maxAmountsIn – sometimes only a single wei. The vault checks that amountInRaw does not exceed maxAmountsIn and reverts with the error AmountInAboveMax when the condition is violated. Consequently, any liquidity removal that triggers the admin‑fee path fails, causing the transaction to revert and leaving the user’s liquidity permanently locked in the pool. The issue manifests only when the admin fee percent is greater than zero, making it appear intermittently and difficult to detect because the discrepancy is extremely small. Affected parties include liquidity providers who cannot withdraw their funds, the protocol that cannot collect its admin fees, and any downstream users who rely on the pool’s availability. The bug was discovered during a formal audit when a test case that called removeLiquidityProportional consistently reverted with the AmountInAboveMax error. From a user’s perspective the UI would show a failed withdrawal, no tokens returned, and the balance appearing unchanged, contrary to the expectation that the withdrawal would succeed. The root cause is an off‑by‑one rounding mismatch in the fee‑transfer logic, a classic precision‑error class of bug. To remediate, the contract should introduce a small safety buffer to the maxAmountsIn values (for example adding one wei) or slightly lower the minBptAmountOut requirement, thereby accommodating the vault’s rounding behaviour and ensuring the withdrawal can complete without reverting.
