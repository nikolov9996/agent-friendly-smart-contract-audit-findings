---
id: 20678
severity: "High"
---

# When borrowers repay USDS, it is sent to the wrong address, allowing anyone to burn Protocol Owned Liquidity and build bad debt for USDS

## Description

When a user repays the USDS he has borrowed, it is taken from him and kept for burning. The Liquidizer contract is updated with the new amount repaid. The USDS is burnt whenever the `performUpkeep` function is called on Liquidizer by the Upkeep contract during upkeep.

The USDS collected is sent to the USDS contract which can be burned whenever `burnTokensInContract` is called. The amount of USDS to be burnt in the Liquidizer contract is also increased by the `incrementBurnableUSDS` call. This increases the `usdsThatShouldBeBurned` variable on the Liquidizer.

```solidity
function repayUSDS( uint256 amountRepaid ) external nonReentrant{
      ...		
      usds.safeTransferFrom(msg.sender, address(usds), amountRepaid);

      // Have USDS remember that the USDS should be burned
      liquidizer.incrementBurnableUSDS( amountRepaid );
      ...
}
```

During upkeep, the Liquidizer first checks if it has enough USDS balance to burn i.e `usdsBalance >= usdsThatShouldBeBurned`. If it does it burns them else it converts Protocol Owned Liquidity (POL) to USDS and burns it to cover the deficit. Burning POL allows the protocol to cover bad debt from liquidation.

```solidity
function _possiblyBurnUSDS() internal{
       ...
	uint256 usdsBalance = usds.balanceOf(address(this));
	if ( usdsBalance >= usdsThatShouldBeBurned )
	{
		// Burn only up to usdsThatShouldBeBurned.
		// Leftover USDS will be kept in this contract in case it needs to be burned later.
		_burnUSDS( usdsThatShouldBeBurned );
    		usdsThatShouldBeBurned = 0;
	}
	else
	{
		// The entire usdsBalance will be burned - but there will still be an outstanding balance to burn later
		_burnUSDS( usdsBalance );
		usdsThatShouldBeBurned -= usdsBalance;

		// As there is a shortfall in the amount of USDS that can be burned, liquidate some Protocol Owned Liquidity and
		// send the underlying tokens here to be swapped to USDS
		dao.withdrawPOL(salt, usds, PERCENT_POL_TO_WITHDRAW);
		dao.withdrawPOL(dai, usds, PERCENT_POL_TO_WITHDRAW);
	}
}
```

Since the `usdsThatShouldBeBurned` variable will always be increased without increasing the Liquidizer balance, it will always sell POL to cover the increase.

If the POL is exhausted, the protocol cannot cover bad debt generated from liquidations. This will affect the price of USDS negatively.

An attacker can borrow and repay multiple times to exhaust POL and create bad debt or it could just be done over time as users repay their USDS.

## Proof of Concept

This test can be run in [CollateralAndLiquidity.t.sol](https://github.com/code-423n4/2024-01-salty/blob/main/src/stable/tests/CollateralAndLiquidity.t.sol).

```solidity
function testBurnPOL() public {
        // setup
        vm.prank(address(collateralAndLiquidity));
		usds.mintTo(address(dao), 20000 ether);

		vm.prank(address(teamVestingWallet));
		salt.transfer(address(dao), 10000 ether);

		vm.prank(DEPLOYER);
		dai.transfer(address(dao), 10000 ether);
        // create Protocol Owned Liquidity (POL)
        vm.startPrank(address(dao));
		collateralAndLiquidity.depositLiquidityAndIncreaseShare(salt, usds, 10000 ether, 10000 ether, 0, block.timestamp, false );
		collateralAndLiquidity.depositLiquidityAndIncreaseShare(dai, usds, 10000 ether, 10000 ether, 0, block.timestamp, false );
		vm.stopPrank();

        bytes32 poolIDA = PoolUtils._poolID(salt, usds);
		bytes32 poolIDB = PoolUtils._poolID(dai, usds);
		assertEq( collateralAndLiquidity.userShareForPool(address(dao), poolIDA), 20000 ether);
		assertEq( collateralAndLiquidity.userShareForPool(address(dao), poolIDB), 20000 ether);

        // Alice deposits collateral
        vm.startPrank(address(alice));
        wbtc.approve(address(collateralAndLiquidity), type(uint256).max);
        weth.approve(address(collateralAndLiquidity), type(uint256).max);
        collateralAndLiquidity.depositCollateralAndIncreaseShare(wbtc.balanceOf(alice), weth.balanceOf(alice), 0, block.timestamp, true );
        
        // Alice performs multiple borrows and repayments, increasing the 
        // usdsThatShouldBeBurned variable in Liquidizer
        for (uint i; i < 100; i++){
            vm.startPrank(alice);
            uint256 maxUSDS = collateralAndLiquidity.maxBorrowableUSDS(alice);
		    collateralAndLiquidity.borrowUSDS( maxUSDS );
            uint256 borrowed = collateralAndLiquidity.usdsBorrowedByUsers(alice);
            collateralAndLiquidity.repayUSDS(borrowed);
        }
        
        vm.startPrank(address(upkeep));
        // perform upkeep multiple times to cover bad debt
        // breaks when POL is exhausted
        for(;;){
            (, uint reserve1) = pools.getPoolReserves(dai, usds);
            if(reserve1 * 99 / 100 < 100) break;
            liquidizer.performUpkeep();
        }

        assertGt(liquidizer.usdsThatShouldBeBurned(), usds.balanceOf(address(liquidizer)));
}
```

## Recommendation

Send the repaid USDS to the Liquidizer.

The stablecoin framework: /stablecoin, /price_feed, WBTC/WETH collateral, PriceAggregator, price feeds and USDS have been removed:

<https://github.com/othernet-global/salty-io/commit/88b7fd1f3f5e037a155424a85275efd79f3e9bf9>

## Derived Narrative

The following field is derived content and may not be source-grounded:

When a borrower calls the repayUSDS function, the contract transfers the specified amount of USDS from the borrower to the USDS token contract instead of to the Liquidizer contract that is responsible for tracking how much USDS should be burned. At the same time the function calls liquidizer.incrementBurnableUSDS, which increases the internal variable usdsThatShouldBeBurned. Because the transferred USDS never arrives in the Liquidizer, the contract’s USDS balance remains unchanged while the burnable amount grows. During each upkeep cycle the Liquidizer checks whether its USDS balance is at least the amount recorded in usdsThatShouldBeBurned. If the balance is insufficient, the contract withdraws a percentage of its Protocol Owned Liquidity (POL) and swaps it for USDS so that the shortfall can be burned. Consequently, every repayment that does not actually increase the Liquidizer’s USDS balance forces the protocol to liquidate POL to cover the artificial deficit. An attacker can exploit this mismatch by repeatedly borrowing the maximum amount of USDS and immediately repaying it. Each repayment inflates usdsThatShouldBeBurned without providing any USDS to the Liquidizer, causing the contract to repeatedly withdraw and burn POL. Over many iterations the POL pool can be exhausted, leaving the protocol unable to cover bad debt generated by liquidations. This situation can depress the market price of USDS because the protocol loses the safety buffer normally provided by POL. The vulnerability was discovered during a formal audit when a test script performed a loop of borrow‑repay operations and observed that usdsThatShouldBeBurned grew far beyond the Liquidizer’s actual USDS balance, eventually causing the POL withdrawal logic to fail. The bug is subtle because the repayment transaction succeeds and the transferred USDS appears in the USDS contract, so users see no immediate error; the internal accounting mismatch is hidden from external observers, making the drain of liquidity difficult to detect during normal operation. To remediate the issue the repayment flow must be corrected so that the repaid USDS are sent directly to the Liquidizer, or the accounting logic must be adjusted to decrement usdsThatShouldBeBurned when USDS are transferred elsewhere. Aligning the token flow with the burn accounting eliminates the unnecessary POL liquidation and restores the protocol’s ability to cover bad debt.
