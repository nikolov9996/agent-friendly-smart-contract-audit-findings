---
id: 21555
severity: "High"
---

# Most users won’t be able to claim their share of Uniswap fees

## Description

Users should be able to claim Uniswap fees for their current liquidity position regardless of their pending vestings, or cliff. But most users won’t be able to claim those Uniswap fees.

It is also possible that they won’t be able to claim their vesting if they accumulate sufficient unclaimed Uniswap fees.

## Proof of Concept

This POC shows how after one user claims their share of the fees, there are no more fee tokens to collect for the next claims, and the transactions revert.

  1. Add the import to the top of `test/ILOPool.t.sol`.
  2. Add the test to the `ILOPoolTest` contract in `test/ILOPool.t.sol`.
  3. Run `forge test --mt testClaimFeesRevert`.

```solidity
import '../lib/v3-core/contracts/interfaces/IUniswapV3Pool.sol';

function testClaimFeesRevert() external {
  _launch();
  vm.warp(VEST_START_0 + 10);

  uint256 tokenId = IILOPool(iloPool).tokenOfOwnerByIndex(INVESTOR, 0);
  uint256 tokenId2 = IILOPool(iloPool).tokenOfOwnerByIndex(INVESTOR_2, 0);

  IUniswapV3Pool uniV3Pool = IUniswapV3Pool(projectId);

  // INVESTOR and INVESTOR_2 burn their liquidity and obtain their tokens

  vm.prank(INVESTOR);
  IILOPool(iloPool).claim(tokenId);

  vm.prank(INVESTOR_2);
  IILOPool(iloPool).claim(tokenId2);

  // Generate some fees via a flash loan
  uniV3Pool.flash(address(this), 1e8, 1e8, "");

  // INVESTOR claims their corresponding part of the fees
  // Only the first one to claim has better odds of claiming successfully
  vm.prank(INVESTOR);
  IILOPool(iloPool).claim(tokenId);

  // INVESTOR_2 can't claim their part of the fees as the transaction will revert
  // It reverts with ST (SafeTransfer) as it is trying to transfer tokens the contract doesn't have
  // The fees for INVESTOR_2 were already taken
  vm.prank(INVESTOR_2);
  vm.expectRevert(bytes("ST"));
  IILOPool(iloPool).claim(tokenId2);

  // Generate more fees
  uniV3Pool.flash(address(this), 1e6, 1e6, "");

  // Even if some new fees are available, they might not be enough to pay back the owed ones to INVESTOR_2
  vm.prank(INVESTOR_2);
  vm.expectRevert(bytes("ST"));
  IILOPool(iloPool).claim(tokenId2);
}

function uniswapV3FlashCallback(uint256, uint256, bytes memory) external {
  deal(USDC, address(this), IERC20(USDC).balanceOf(address(this)) * 2);
  deal(SALE_TOKEN, address(this), IERC20(SALE_TOKEN).balanceOf(address(this)) * 2);

  IERC20(USDC).transfer(projectId, IERC20(USDC).balanceOf(address(this)));
  IERC20(SALE_TOKEN).transfer(projectId, IERC20(SALE_TOKEN).balanceOf(address(this)));
}
```

## Recommendation

Here’s an suggestion on how this could be solved. The idea is to only `collect()` the tokens corresponding to the liquidity of the `tokenId` position. So that the next user can also claim their share.

```solidity
function claim(uint256 tokenId) external payable override isAuthorizedForToken(tokenId)
    returns (uint256 amount0, uint256 amount1)
{
  uint128 collect0;
  uint128 collect1;

  uint128 liquidity2Claim = _claimableLiquidity(tokenId);
  IUniswapV3Pool pool = IUniswapV3Pool(_cachedUniV3PoolAddress);
  {
    IILOManager.Project memory _project = IILOManager(MANAGER).project(address(pool));
    uint128 positionLiquidity = position.liquidity;

    // get amount of token0 and token1 that pool will return for us
    (amount0, amount1) = pool.burn(TICK_LOWER, TICK_UPPER, liquidity2Claim);

    collect0 = amount0;
    collect1 = amount1;

    // get amount of token0 and token1 after deduct platform fee
    (amount0, amount1) = _deductFees(amount0, amount1, _project.platformFee);

    ...
    
    uint256 fees0 = FullMath.mulDiv(
                    feeGrowthInside0LastX128 - position.feeGrowthInside0LastX128,
                    positionLiquidity,
                    FixedPoint128.Q128
                );
    
    uint256 fees1 = FullMath.mulDiv(
                        feeGrowthInside1LastX128 - position.feeGrowthInside1LastX128,
                        positionLiquidity,
                        FixedPoint128.Q128
                    );

    collect0 += fees0;
    collect1 += fees1;

    // amount of fees after deduct performance fee
    (fees0, fees1) = _deductFees(fees0, fees1, _project.performanceFee);

    ...
  }

  (uint128 amountCollected0, uint128 amountCollected1) = pool.collect(
    address(this),
    TICK_LOWER,
    TICK_UPPER,
    collect0,
    collect1
  );
  
  ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the fee‑claiming routine of a Uniswap V3 based liquidity‑vesting contract. The contract is supposed to let every liquidity provider withdraw the portion of protocol fees that corresponds to their current position, regardless of any pending vesting schedule. In practice the claim() function first burns the caller’s liquidity, then adds the accumulated fee amounts (fees0 and fees1) to a variable called collect0/collect1 and finally invokes pool.collect to transfer those tokens to the contract. The root cause is that the amount passed to pool.collect is calculated using the total liquidity of the position (positionLiquidity) instead of the actual liquidity that is being claimed (liquidity2Claim). As a result the contract attempts to collect the full fee entitlement for the whole position each time a claim is made, even after a previous claim has already withdrawn those fees. When the first user calls claim, the pool returns the expected fee tokens and the contract’s internal balance is reduced to zero. A subsequent user calling claim for a different tokenId triggers the same collect call, but the contract no longer holds the required fee tokens, causing the pool’s safe‑transfer to revert with the error code “ST”. This failure also blocks the vesting withdrawal path because the contract cannot satisfy the fee transfer that is part of the vesting logic. The impact is that legitimate users see their expected refunds disappear; the UI may show a successful claim transaction for the first user, while later users receive a reverted transaction and see no tokens credited, effectively losing access to their share of fees. The issue manifests only when multiple distinct tokenIds share the same underlying Uniswap pool and claim sequentially, which is a common scenario in multi‑investor offerings. It was discovered during a systematic forge test that simulated two investors claiming fees after a flash‑loan generated fee accrual; the second claim consistently reverted. The bug is subtle because the first claim succeeds and the code appears to follow the Uniswap fee‑collection pattern, making the over‑collection logic easy to overlook. To remediate, the contract should compute fees based on the exact amount of liquidity being claimed, limit the collect parameters to the caller’s entitlement, and reset fee‑tracking variables after each successful claim. In broader terms, this is a classic case of improper accounting of shared resources leading to double‑spending of fee tokens, violating the contract’s financial invariants and breaking user expectations that “my share of fees should always be claimable”.
