---
id: 13875
severity: "High"
---

# fees sent to QuantAMMAdmin is stuck forever as there is no function to retrieve them

## Description

When a user removes liquidity from the pool he pays fees and a portion of the fees is liquidity added back for QuantAMMAdmin

Those funds are stuck in, and can't be removed as there is no mapping or NFT minted for those shares so any attempt to removeliquidity will revert

Here is the call inside onAfterRemoveLiquidity to add fees to quantAMMAdmin
```solidity
File: UpliftOnlyExample.sol
536:         if (localData.adminFeePercent > 0) {
537:             _vault.addLiquidity(
538:                 AddLiquidityParams({
539:                     pool: localData.pool,
540:                     to: IUpdateWeightRunner(_updateWeightRunner).getQuantAMMAdmin(),
541:                     maxAmountsIn: localData.accruedQuantAMMFees,
542:                     minBptAmountOut: localData.feeAmount.mulDown(localData.adminFeePercent) / 1e18,
543:                     kind: AddLiquidityKind.PROPORTIONAL,
544:                     userData: bytes("")
545:                 })
```

In removeLiquidityProportional there is a check for the length of poolsFeeData in this case, would be zero and any attempt to remove will revert
```solidity
File: UpliftOnlyExample.sol
265:     function removeLiquidityProportional(
266:         uint256 bptAmountIn,
267:         uint256[] memory minAmountsOut,
268:         bool wethIsEth,
269:         address pool
270:     ) external payable saveSender(msg.sender) returns (uint256[] memory amountsOut) {
271:         uint depositLength = poolsFeeData[pool][msg.sender].length;
272: 
273:         if (depositLength == 0) {
274:             revert WithdrawalByNonOwner(msg.sender, pool, bptAmountIn);
275:         }
```

POC
Add this anywhere in UpliftExample.t.sol
```solidity
    function testRemoveLiquidityStuckAdmin_Fees() public {
        vm.prank(address(vaultAdmin));
        updateWeightRunner.setQuantAMMUpliftFeeTake(0.5e18);
        vm.stopPrank();

        // Add liquidity so bob has BPT to remove liquidity.
        uint256[] memory maxAmountsIn = [dai.balanceOf(bob), usdc.balanceOf(bob)].toMemoryArray();

        vm.prank(bob);
        upliftOnlyRouter.addLiquidityProportional(pool, maxAmountsIn, bptAmount, false, bytes(""));
        vm.stopPrank();

        uint256[] memory minAmountsOut = [uint256(0), uint256(0)].toMemoryArray();

        vm.startPrank(bob);
        upliftOnlyRouter.removeLiquidityProportional(bptAmount, minAmountsOut, false, pool);
        vm.stopPrank();
        BaseVaultTest.Balances memory balancesAfter = getBalances(updateWeightRunner.getQuantAMMAdmin());

        //trying to remove liquidity added to QuantAMMAdmin with the value added from bob removing liquidity the remove attempt will revert with WithdrawalByNonOwner error
        vm.prank(updateWeightRunner.getQuantAMMAdmin());
        vm.expectRevert();
        upliftOnlyRouter.removeLiquidityProportional(500000000000000000, minAmountsOut, false, pool);
        vm.stopPrank();

    }
Loss of Funds: Fees added as liquidity for QuantAMMAdmin are stuck and cannot be removed.
```

## Proof of Concept

Add this anywhere in UpliftExample.t.sol
```solidity
    function testRemoveLiquidityStuckAdmin_Fees() public {
        vm.prank(address(vaultAdmin));
        updateWeightRunner.setQuantAMMUpliftFeeTake(0.5e18);
        vm.stopPrank();

        // Add liquidity so bob has BPT to remove liquidity.
        uint256[] memory maxAmountsIn = [dai.balanceOf(bob), usdc.balanceOf(bob)].toMemoryArray();

        vm.prank(bob);
        upliftOnlyRouter.addLiquidityProportional(pool, maxAmountsIn, bptAmount, false, bytes(""));
        vm.stopPrank();

        uint256[] memory minAmountsOut = [uint256(0), uint256(0)].toMemoryArray();

        vm.startPrank(bob);
        upliftOnlyRouter.removeLiquidityProportional(bptAmount, minAmountsOut, false, pool);
        vm.stopPrank();
        BaseVaultTest.Balances memory balancesAfter = getBalances(updateWeightRunner.getQuantAMMAdmin());

        //trying to remove liquidity added to QuantAMMAdmin with the value added from bob removing liquidity the remove attempt will revert with WithdrawalByNonOwner error
        vm.prank(updateWeightRunner.getQuantAMMAdmin());
        vm.expectRevert();
        upliftOnlyRouter.removeLiquidityProportional(500000000000000000, minAmountsOut, false, pool);
        vm.stopPrank();

    }
```

## Recommendation

create a new array while creating as done for normal addition

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a permanent lock‑up of protocol fees that are allocated to the QuantAMMAdmin address when a liquidity provider removes liquidity from a pool. When a user calls the remove‑liquidity function, a portion of the collected fees is transferred to the admin by invoking the vault’s addLiquidity routine with the admin address as the recipient. The contract does not create any accounting entry – such as a mapping entry or an NFT – that represents the admin’s share of the pool. Consequently, the internal data structure poolsFeeData for the admin address remains empty. Later, when the admin (or any other actor) attempts to withdraw the accumulated fee liquidity using the same removeLiquidityProportional function, the function checks the length of poolsFeeData[pool][msg.sender] and reverts with WithdrawalByNonOwner because the length is zero. This means the fee liquidity is effectively trapped forever, unable to be redeemed or transferred. The issue was discovered during a targeted audit test that added liquidity, removed it to generate admin fees, and then attempted to withdraw those fees, observing the revert. It is hard to notice because the admin address never appears to hold any explicit token balance; the vault’s internal accounting simply shows no deposit for that address, masking the presence of the locked value. The impact is a loss of funds: the protocol’s fee revenue intended for the admin cannot be accessed, reducing the economic incentives for the protocol maintainers and potentially affecting the overall fee distribution model. The problem occurs whenever the admin fee percentage is non‑zero and a liquidity removal triggers fee allocation, which is a common operation for any user. Affected parties include the protocol administrators who expect to receive fees, as well as any stakeholders relying on proper fee accounting. To remediate the issue, the contract should create a proper accounting entry for the admin’s fee shares – for example by initializing a new array or minting an NFT that records the admin’s liquidity position – and provide a dedicated withdrawal function that references this entry, ensuring that the admin can later redeem the locked liquidity. In user‑facing terms, a user who removes liquidity sees the expected amount of tokens returned, but the admin’s fee balance appears to stay at zero even though fees were added, leading to a discrepancy between expected fee receipts and actual on‑chain state. This class of bug is an accounting omission that results in unrecoverable liquidity, similar to other cases where protocol‑level fees are sent to an address without a corresponding ownership record.
