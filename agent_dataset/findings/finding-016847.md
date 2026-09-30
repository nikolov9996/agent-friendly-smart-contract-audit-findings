---
id: 16847
severity: "Medium"
---

# It is possible that, after swapping, extra input token amount is transferred from user to pool but pool does not give user output token amount that corresponds to the extra input token amount

## Description

When calling the `swap` function below, the following `_swapCallback` function is further called for calling the `algebraSwapCallback` function in the callee contract, which is `msg.sender`; such contract could be implemented by a third party especially for non-technical users. There is no guarantee that such contract will not send more input token amount than required to the pool. When this happens, the output token amount corresponding to the extra input token amount will not be transferred from the pool to the recipient after the swap. As a result, the user sends extra input token amount to the pool but does not receive any output token amount corresponding to the extra input token amount. Disputes between the user and protocol can occur because of this.

[AlgebraPool.sol#L580-L586](https://github.com/code-423n4/2022-09-quickswap/blob/main/src/core/contracts/AlgebraPool.sol#L580-L586)

```solidity
  function _swapCallback(
    int256 amount0,
    int256 amount1,
    bytes calldata data
  ) private {
    IAlgebraSwapCallback(msg.sender).algebraSwapCallback(amount0, amount1, data);
  }
```

[AlgebraPool.sol#L589-L623](https://github.com/code-423n4/2022-09-quickswap/blob/main/src/core/contracts/AlgebraPool.sol#L589-L623)

```solidity
  function swap(
    address recipient,
    bool zeroToOne,
    int256 amountRequired,
    uint160 limitSqrtPrice,
    bytes calldata data
  ) external override returns (int256 amount0, int256 amount1) {
    uint160 currentPrice;
    int24 currentTick;
    uint128 currentLiquidity;
    uint256 communityFee;
    // function _calculateSwapAndLock locks globalState.unlocked and does not release
    (amount0, amount1, currentPrice, currentTick, currentLiquidity, communityFee) = _calculateSwapAndLock(zeroToOne, amountRequired, limitSqrtPrice);

    if (zeroToOne) {
      if (amount1 < 0) TransferHelper.safeTransfer(token1, recipient, uint256(-amount1)); // transfer to recipient

      uint256 balance0Before = balanceToken0();
      _swapCallback(amount0, amount1, data); // callback to get tokens from the caller
      require(balance0Before.add(uint256(amount0)) <= balanceToken0(), 'IIA');
    } else {
      if (amount0 < 0) TransferHelper.safeTransfer(token0, recipient, uint256(-amount0)); // transfer to recipient

      uint256 balance1Before = balanceToken1();
      _swapCallback(amount0, amount1, data); // callback to get tokens from the caller
      require(balance1Before.add(uint256(amount1)) <= balanceToken1(), 'IIA');
    }

    if (communityFee > 0) {
      _payCommunityFee(zeroToOne ? token0 : token1, communityFee);
    }

    emit Swap(msg.sender, recipient, amount0, amount1, currentPrice, currentLiquidity, currentTick);
    globalState.unlocked = true; // release after lock in _calculateSwapAndLock
  }
```

## Proof of Concept

First, in `src\core\contracts\test\`, please add the following test callee contract.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity =0.7.6;

import '../interfaces/IERC20Minimal.sol';
import '../libraries/SafeCast.sol';
import '../interfaces/callback/IAlgebraMintCallback.sol';
import '../interfaces/callback/IAlgebraSwapCallback.sol';
import '../interfaces/IAlgebraPool.sol';

contract TestCalleeForSendingExtraTokenAmount is IAlgebraMintCallback, IAlgebraSwapCallback {
  using SafeCast for uint256;

  function swapExact0For1(
    address pool,
    uint256 amount0In,
    address recipient,
    uint160 limitSqrtPrice
  ) external {
    IAlgebraPool(pool).swap(recipient, true, amount0In.toInt256(), limitSqrtPrice, abi.encode(msg.sender));
  }

  event SwapCallback(int256 amount0Delta, int256 amount1Delta);

  function algebraSwapCallback(
    int256 amount0Delta,
    int256 amount1Delta,
    bytes calldata data
  ) external override {
    address sender = abi.decode(data, (address));

    emit SwapCallback(amount0Delta, amount1Delta);

    // simulate a situation where extra token amount is sent to the pool
    if (amount0Delta > 0) {
      IERC20Minimal(IAlgebraPool(msg.sender).token0()).transferFrom(sender, msg.sender, uint256(amount0Delta) + 1e9);
    } else if (amount1Delta > 0) {
      IERC20Minimal(IAlgebraPool(msg.sender).token1()).transferFrom(sender, msg.sender, uint256(amount1Delta) + 1e9);
    } else {
      assert(amount0Delta == 0 && amount1Delta == 0);
    }
  }

  event MintResult(uint256 amount0Owed, uint256 amount1Owed, uint256 resultLiquidity);

  function mint(
    address pool,
    address recipient,
    int24 bottomTick,
    int24 topTick,
    uint128 amount
  )
    external
    returns (
      uint256 amount0Owed,
      uint256 amount1Owed,
      uint256 resultLiquidity
    )
  {
    (amount0Owed, amount1Owed, resultLiquidity) = IAlgebraPool(pool).mint(msg.sender, recipient, bottomTick, topTick, amount, abi.encode(msg.sender));
    emit MintResult(amount0Owed, amount1Owed, resultLiquidity);
  }

  event MintCallback(uint256 amount0Owed, uint256 amount1Owed);

  function algebraMintCallback(
    uint256 amount0Owed,
    uint256 amount1Owed,
    bytes calldata data
  ) external override {
    address sender = abi.decode(data, (address));

    if (amount0Owed > 0) IERC20Minimal(IAlgebraPool(msg.sender).token0()).transferFrom(sender, msg.sender, amount0Owed);
    if (amount1Owed > 0) IERC20Minimal(IAlgebraPool(msg.sender).token1()).transferFrom(sender, msg.sender, amount1Owed);

    emit MintCallback(amount0Owed, amount1Owed);
  }
}
```

Then, please add the following test in the `AlgebraPool` `describe` block in `src\core\test\AlgebraPool.spec.ts`. This test will pass to demonstrate the described scenario.

```typescript
    describe('POC', () => {
        it('It is possible that, after swapping, extra input token amount is transferred from user to pool but pool does not give user output token amount that corresponds to the extra input token amount', async () => {
            /** set up contracts */
            const PoolDeployerFactory = await ethers.getContractFactory('AlgebraPoolDeployer');
            const poolDeployer = await PoolDeployerFactory.deploy();
      
            const FactoryFactory = await ethers.getContractFactory('AlgebraFactory');
            const factory = await FactoryFactory.deploy(poolDeployer.address, vaultAddress);
      
            const TokenFactory = await ethers.getContractFactory('TestERC20');
            const token0 = await TokenFactory.deploy(BigNumber.from(2).pow(255));
            const token1 = await TokenFactory.deploy(BigNumber.from(2).pow(255));
          
            const calleeContractFactory = await ethers.getContractFactory('TestCalleeForSendingExtraTokenAmount');
            const swapTargetCallee = await calleeContractFactory.deploy();
      
            const MockTimeAlgebraPoolDeployerFactory = await ethers.getContractFactory('MockTimeAlgebraPoolDeployer')
            const mockTimePoolDeployer = await MockTimeAlgebraPoolDeployerFactory.deploy();
            const tx = await mockTimePoolDeployer.deployMock(
              factory.address,
              token0.address,
              token1.address
            )
            const receipt = await tx.wait()
            const poolAddress = receipt.events?.[1].args?.pool;
      
            const MockTimeAlgebraPoolFactory = await ethers.getContractFactory('MockTimeAlgebraPool');
            const pool = MockTimeAlgebraPoolFactory.attach(poolAddress);
      
            await pool.initialize(encodePriceSqrt(1, 1));
      
            await token0.approve(swapTargetCallee.address, constants.MaxUint256);
            await token1.approve(swapTargetCallee.address, constants.MaxUint256);
            await swapTargetCallee.mint(pool.address, wallet.address, minTick, maxTick, expandTo18Decimals(1));
            /** */
      
            // set up user
            const user = other;
            await token0.connect(user).mint(user.address, expandTo18Decimals(1));
            await token0.connect(user).approve(swapTargetCallee.address, constants.MaxUint256);
      
            const token0BalancePoolBefore = await token0.balanceOf(pool.address);
            const token0BalanceUserBefore = await token0.balanceOf(user.address);
      
            const token1BalancePoolBefore = await token1.balanceOf(pool.address);
            const token1BalanceUserBefore = await token1.balanceOf(user.address);
      
            // amountIn and amountOut are the expected token amounts to be in and out after the upcoming swap
            const amountIn = expandTo18Decimals(1).div(1000000000);
            const amountOut = -999899999;
      
            await expect(
              // the TestCalleeForSendingExtraTokenAmount contract's algebraSwapCallback function simulates a situation where extra token0 amount is transferred from user to pool
              swapTargetCallee.connect(user).swapExact0For1(pool.address, amountIn, user.address, MIN_SQRT_RATIO.add(1))
            ).to.be.emit(swapTargetCallee, 'SwapCallback').withArgs(amountIn, amountOut);
      
            // after the swap, pool has received the extra token0 amount that was transferred from user
            const token0BalancePoolAfter = await token0.balanceOf(pool.address);
            const token0BalanceUserAfter = await token0.balanceOf(user.address);
            expect(token0BalancePoolAfter).to.be.gt(token0BalancePoolBefore.add(amountIn));
            expect(token0BalanceUserAfter).to.be.lt(token0BalanceUserBefore.sub(amountIn));
      
            // yet, pool does not give user the token1 amount that corresponds to the extra token0 amount
            const token1BalancePoolAfter = await token1.balanceOf(pool.address);
            const token1BalanceUserAfter = await token1.balanceOf(user.address);
            expect(token1BalancePoolAfter).to.be.eq(token1BalancePoolBefore.add(amountOut));
            expect(token1BalanceUserAfter).to.be.eq(token1BalanceUserBefore.sub(amountOut));
        })
    })
```

## Recommendation

[AlgebraPool.sol#L608](https://github.com/code-423n4/2022-09-quickswap/blob/main/src/core/contracts/AlgebraPool.sol#L608) can be updated to the following code.

```solidity
          require(balance0Before.add(uint256(amount0)) == balanceToken0(), 'IIA');
```

Also, [AlgebraPool.sol#L614](https://github.com/code-423n4/2022-09-quickswap/blob/main/src/core/contracts/AlgebraPool.sol#L614) can be updated to the following code.

```solidity
          require(balance1Before.add(uint256(amount1)) == balanceToken1(), 'IIA');
```

Going to award as Medium due to sponsor confirming. I think this is more reasonably a QA issue since it assumes a bad integration. Will mark other similar issues as dupe.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the swap workflow of the AlgebraPool contract. When a user initiates a swap, the pool calls a private function _swapCallback that forwards control to an external contract supplied by the caller (msg.sender). This external contract implements the IAlgebraSwapCallback interface and is expected to transfer the exact amount of input tokens required for the swap back to the pool. However, the pool only verifies that the post‑callback balance of the input token is greater than or equal to the expected balance using a "<=" comparison (require(balanceBefore.add(uint256(amount)) <= balanceAfter)). If the callback deliberately or accidentally sends more input tokens than required, the inequality still holds, allowing the pool to accept the surplus without adjusting the amount of output tokens sent to the recipient. Consequently, the user loses the extra input token amount while receiving no corresponding additional output tokens. The bug manifests whenever the callback contract transfers a higher amount than the delta computed by _calculateSwapAndLock, which can happen with malicious callbacks or poorly written integration contracts for non‑technical users. It was discovered during a targeted audit test that crafted a callback contract to transfer "amount + 1e9" tokens, demonstrating that the pool retains the excess. The issue is subtle because normal swaps involve exact token transfers, so the invariant check appears to work under typical conditions, making the discrepancy easy to overlook. This class of bug is an insufficient post‑condition validation (using "<=" instead of equality) that breaks the accounting assumption that the pool’s token balance changes exactly by the amount calculated for the swap. The impact is a loss of funds for the swap initiator, potential disputes, and erosion of trust in the protocol’s fairness. The appropriate fix is to replace the "<=" checks with exact equality checks (require(balanceBefore.add(uint256(amount)) == balanceAfter)) for both input token directions, ensuring that any deviation from the expected transfer amount aborts the transaction. By enforcing strict balance matching, the pool guarantees that every input token amount transferred to it is compensated with the correct amount of output tokens, preserving the intended economic invariants of the swap operation.
