---
id: 25100
severity: "Low/Info"
---

# InRatioSwap fuzz test shows error up to 1e10 of a token with 18 decimal places

## Description

Performed fuzz tests of the InRatioSwap.getInRatioSwap() function showing that the error is always smaller than 1e10. Here is the test for reference: ​

```solidity
// SPDX-License-Identifier: UNLICENSED​ pragma solidity ^0.8.13;​
​
import {Test, console} from "forge-std/Test.sol";​
import {IERC20Metadata} from
```

"contracts/deps/OpenZeppelinV5/IERC20Metadata.sol";​

```solidity
import {SafeERC20} from "contracts/deps/OpenZeppelinV5/SafeERC20.sol";​
import {IPancakeV3Pool} from
```

"contracts/interfaces/pancake/IPancakeV3Pool.sol";​

```solidity
import "contracts/interfaces/pancake/IPancakeV3PositionManager.sol";​
import "contracts/lib/pancake/InRatioSwap.sol";​
```

​

```solidity
contract InRatioSwapTest is Test {​
    using SafeERC20 for IERC20Metadata;​
    address token0 = 0x55d398326f99059fF775485246999027B3197955 ;​
    address token1 = 0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409;​
    V3PancakePool pool =
```

V3PancakePool.wrap(0xbF72B6485E4b31601aFe7B0a1210Be2004D2B1d6);​ IPancakeV3PositionManager positionManager = IPancakeV3PositionManager(0x46A15B0b27311cedF172AB29E4f4766fbE7F4364);​

```solidity
int24 currentTick;​

uint24 fee = 100;​
function setUp() public {​
```

vm.createSelectFork("[https://bsc.meowrpc.com",](<https://bsc.meowrpc.com&quot/>) 37430470);​ (, currentTick) = pool.sqrtPriceX96AndTick();​ IERC20Metadata(token0).approve(address(positionManager), type(uint256).max);​ IERC20Metadata(token1).approve(address(positionManager), type(uint256).max);​ }​ function testFuzz(uint256 token0Amount, uint256 token1Amount, int24 tickLower, int24 tickUpper) public {​ vm.assume(tickLower < tickUpper);​ vm.assume(tickLower > TickMath.MIN_TICK);​ vm.assume(tickUpper < TickMath.MAX_TICK);​ token0Amount = token0Amount % IERC20Metadata(token0).balanceOf(V3PancakePool.unwrap(pool));​ token1Amount = token1Amount % IERC20Metadata(token1).balanceOf(V3PancakePool.unwrap(pool));​ deal(token0, address(this), token0Amount);​ deal(token1, address(this), token1Amount);​

```solidity
(uint256 amountIn,, bool zeroForOne,) = InRatioSwap.getInRatioSwap(pool, tickLower, tickUpper, token0Amount,
```

token1Amount);​ ​ uint160 swapThresholdPrice = zeroForOne ? TickMath.MIN_SQRT_RATIO + 1 : TickMath.MAX_SQRT_RATIO - 1; ​

```solidity
if (amountIn != 0)​
IPancakeV3Pool(V3PancakePool.unwrap(pool)).swap(address(this),
```

zeroForOne, int256(amountIn), swapThresholdPrice, "");​ uint256 amount0ToMint = IERC20Metadata(token0).balanceOf(address(this));​ uint256 amount1ToMint = IERC20Metadata(token1).balanceOf(address(this));​ try ​ positionManager.mint(​ IPancakeV3PositionManager.MintParams({​ token0: token0,​ token1: token1,​ fee: fee,​ tickLower: tickLower,​ tickUpper: tickUpper,​ amount0Desired: amount0ToMint,​

amount1Desired: amount1ToMint,​ amount0Min: 0,​ amount1Min: 0,​ recipient: address(this),​ deadline: block.timestamp​ })​ )​ {​ assertLt(IERC20Metadata(token0).balanceOf(address(this)), 1e10);​ assertLt(IERC20Metadata(token1).balanceOf(address(this)), 1e10);​ } ​

```solidity
catch (bytes memory reason) {​
    require(amount0ToMint == 0 || amount1ToMint == 0, "oops");​
```

}​ }​

```solidity
function pancakeV3SwapCallback(int256 amount0Delta, int256 amount1Delta, bytes calldata /*data*/) external {​
    if (amount0Delta > 0)
```

IERC20Metadata(token0).safeTransfer(msg.sender, uint256(amount0Delta));​ else if (amount1Delta > 0) IERC20Metadata(token1).safeTransfer(msg.sender, uint256(amount1Delta));​ } ​ }​

## Proof of Concept

No PoC provided.

## Recommendation

The _deposit() function should return the unused tokens to the msg.sender.
