---
id: 20677
severity: "High"
---

# User can evade `liquidation` by depositing the minimum of tokens and gain time to not be liquidated

## Description

The [CollateralAndLiquidity](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/stable/CollateralAndLiquidity.sol) contract contains a critical vulnerability that allows a user undergoing liquidation to evade the process by manipulating the `user.cooldownExpiration` variable. This manipulation is achieved through the [CollateralAndLiquidity::depositCollateralAndIncreaseShare](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/stable/CollateralAndLiquidity.sol#L70) function, specifically within the [StakingRewards::_increaseUserShare](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/staking/StakingRewards.sol#L57) function (code line [#70](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/staking/StakingRewards.sol#L70)):

```solidity
function _increaseUserShare( address wallet, bytes32 poolID, uint256 increaseShareAmount, bool useCooldown ) internal
	{
	require( poolsConfig.isWhitelisted( poolID ), "Invalid pool" );
	require( increaseShareAmount != 0, "Cannot increase zero share" );

	UserShareInfo storage user = _userShareInfo[wallet][poolID];

	if ( useCooldown )
	if ( msg.sender != address(exchangeConfig.dao()) ) // DAO doesn't use the cooldown
		{
		require( block.timestamp >= user.cooldownExpiration, "Must wait for the cooldown to expire" );

		// Update the cooldown expiration for future transactions
		user.cooldownExpiration = block.timestamp + stakingConfig.modificationCooldown();
		}

	uint256 existingTotalShares = totalShares[poolID];

	// Determine the amount of virtualRewards to add based on the current ratio of rewards/shares.
	// The ratio of virtualRewards/increaseShareAmount is the same as totalRewards/totalShares for the pool.
	// The virtual rewards will be deducted later when calculating the user's owed rewards.
    if ( existingTotalShares != 0 ) // prevent / 0
    	{
		// Round up in favor of the protocol.
		uint256 virtualRewardsToAdd = Math.ceilDiv( totalRewards[poolID] * increaseShareAmount, existingTotalShares );

		user.virtualRewards += uint128(virtualRewardsToAdd);
        totalRewards[poolID] += uint128(virtualRewardsToAdd);
        }

	// Update the deposit balances
	user.userShare += uint128(increaseShareAmount);
	totalShares[poolID] = existingTotalShares + increaseShareAmount;

	emit UserShareIncreased(wallet, poolID, increaseShareAmount);
	}
```

Malicious user can perform front-running of the `liquidation` function by depositing small amounts of tokens to his position, incrementing the `user.cooldownExpiration` variable. Consequently, the execution of the `liquidation` function will be reverted with the error message `Must wait for the cooldown to expire.` This vulnerability could lead to attackers evading liquidation, potentially causing the system to enter into debt as liquidations are avoided.

## Proof of Concept

A test case, named `testUserLiquidationMayBeAvoided`, has been created to demonstrate the potential misuse of the system. The test involves the following steps:

  1. User Alice deposits and borrow the maximum amount.
  2. The collateral price crashes.
  3. Alice maliciously front-runs the `liquidation` execution by depositing a the minimum amount using the `collateralAndLiquidity::depositCollateralAndIncreaseShare` function.
  4. The `liquidation` transaction is reverted by “Must wait for the cooldown to expire” error.

```solidity
// Filename: src/stable/tests/CollateralAndLiquidity.t.sol:TestCollateral
// $ forge test --match-test "testUserLiquidationMayBeAvoided" --rpc-url https://yoururl -vv
//
    function testUserLiquidationMayBeAvoided() public {
        // Liquidatable user can avoid liquidation
        //
		// Have bob deposit so alice can withdraw everything without DUST reserves restriction
        _depositHalfCollateralAndBorrowMax(bob);
        //
        // 1. Alice deposit and borrow the max amount
        // Deposit and borrow for Alice
        _depositHalfCollateralAndBorrowMax(alice);
        // Check if Alice has a position
        assertTrue(_userHasCollateral(alice));
        //
        // 2. Crash the collateral price
        _crashCollateralPrice();
        vm.warp( block.timestamp + 1 days );
        //
        // 3. Alice maliciously front run the liquidation action and deposit a DUST amount
        vm.prank(alice);
		collateralAndLiquidity.depositCollateralAndIncreaseShare(PoolUtils.DUST + 1, PoolUtils.DUST + 1, 0, block.timestamp, false );
        //
        // 4. The function alice liquidation will be reverted by "Must wait for the cooldown to expire"
        vm.expectRevert( "Must wait for the cooldown to expire" );
        collateralAndLiquidity.liquidateUser(alice);
    }
```

## Recommendation

Consider modifying the [liquidation](https://github.com/code-423n4/2024-01-salty/blob/53516c2cdfdfacb662cdea6417c52f23c94d5b5b/src/stable/CollateralAndLiquidity.sol#L154) function as follows:

```solidity
function liquidateUser( address wallet ) external nonReentrant
	{
	require( wallet != msg.sender, "Cannot liquidate self" );

	// First, make sure that the user's collateral ratio is below the required level
	require( canUserBeLiquidated(wallet), "User cannot be liquidated" );

	uint256 userCollateralAmount = userShareForPool( wallet, collateralPoolID );

	// Withdraw the liquidated collateral from the liquidity pool.
	// The liquidity is owned by this contract so when it is withdrawn it will be reclaimed by this contract.
	(uint256 reclaimedWBTC, uint256 reclaimedWETH) = pools.removeLiquidity(wbtc, weth, userCollateralAmount, 0, 0, totalShares[collateralPoolID] );

	// Decrease the user's share of collateral as it has been liquidated and they no longer have it.
--		_decreaseUserShare( wallet, collateralPoolID, userCollateralAmount, true );
++		 _decreaseUserShare( wallet, collateralPoolID, userCollateralAmount, false );

	// The caller receives a default 5% of the value of the liquidated collateral.
	uint256 rewardPercent = stableConfig.rewardPercentForCallingLiquidation();

	uint256 rewardedWBTC = (reclaimedWBTC * rewardPercent) / 100;
	uint256 rewardedWETH = (reclaimedWETH * rewardPercent) / 100;

	// Make sure the value of the rewardAmount is not excessive
	uint256 rewardValue = underlyingTokenValueInUSD( rewardedWBTC, rewardedWETH ); // in 18 decimals
	uint256 maxRewardValue = stableConfig.maxRewardValueForCallingLiquidation(); // 18 decimals
	if ( rewardValue > maxRewardValue )
		{
		rewardedWBTC = (rewardedWBTC * maxRewardValue) / rewardValue;
		rewardedWETH = (rewardedWETH * maxRewardValue) / rewardValue;
		}

	// Reward the caller
	wbtc.safeTransfer( msg.sender, rewardedWBTC );
	weth.safeTransfer( msg.sender, rewardedWETH );

	// Send the remaining WBTC and WETH to the Liquidizer contract so that the tokens can be converted to USDS and burned (on Liquidizer.performUpkeep)
	wbtc.safeTransfer( address(liquidizer), reclaimedWBTC - rewardedWBTC );
	weth.safeTransfer( address(liquidizer), reclaimedWETH - rewardedWETH );

	// Have the Liquidizer contract remember the amount of USDS that will need to be burned.
	uint256 originallyBorrowedUSDS = usdsBorrowedByUsers[wallet];
	liquidizer.incrementBurnableUSDS(originallyBorrowedUSDS);

	// Clear the borrowedUSDS for the user who was liquidated so that they can simply keep the USDS they previously borrowed.
	usdsBorrowedByUsers[wallet] = 0;
	_walletsWithBorrowedUSDS.remove(wallet);

	emit Liquidation(msg.sender, wallet, reclaimedWBTC, reclaimedWETH, originallyBorrowedUSDS);
	}
```

This modification ensures that the `user.cooldownExpiration` expiration check does not interfere with the `liquidation` process, mitigating the identified security risk.

The stablecoin framework: /stablecoin, /price_feed, WBTC/WETH collateral, PriceAggregator, price feeds and USDS have been removed:

<https://github.com/othernet-global/salty-io/commit/88b7fd1f3f5e037a155424a85275efd79f3e9bf9>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a liquidation‑evasion flaw in the CollateralAndLiquidity contract. The contract stores a timestamp called user.cooldownExpiration for each position and requiresthat any share‑increase operation that uses the cooldown flag can only be executed after this timestamp has passed. The internal function _increaseUserShare, which is called by depositCollateralAndIncreaseShare, updates user.cooldownExpiration to block further modifications for a period defined by stakingConfig.modificationCooldown(). When a user is under‑collateralised and a liquidation transaction is submitted, the liquidator calls _decreaseUserShare with the useCooldown flag set to true. Because the same cooldown check is performed, an attacker can front‑run the liquidation by calling depositCollateralAndIncreaseShare with a dust amount of collateral just before the liquidation is executed. This call resets user.cooldownExpiration to a future time, causing the subsequent liquidation call to revert with the error 'Must wait for the cooldown to expire'. The exploit works whenever the attacker can submit a transaction that is mined before the liquidation transaction, which is typical in a public mempool. The impact is that liquidations can be avoided, leaving the protocol with positions that remain under‑collateralised and potentially accumulating debt, while liquidators receive no reward and users see their liquidation attempts fail. The issue is discovered by an audit test (testUserLiquidationMayBeAvoided) that reproduces the revert. It is hard to notice because the cooldown mechanism is intended for normal share adjustments and the liquidation path reuses the same internal function without considering that an attacker could manipulate the timestamp. From a user’s perspective the UI may show a user as liquidatable but the transaction fails, the liquidator receives no funds, and the under‑collateralised user retains their position. The bug belongs to the class of business‑logic state‑manipulation vulnerabilities, specifically a cooldown bypass that breaks accounting assumptions about when a position can be forced closed. The recommended fix is to call _decreaseUserShare with the useCooldown flag set to false during liquidation, or otherwise separate the cooldown logic from liquidation so that the timestamp check does not block forced closures.
