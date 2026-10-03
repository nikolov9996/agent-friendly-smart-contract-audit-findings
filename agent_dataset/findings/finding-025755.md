---
id: 25755
severity: "Crit/High"
---

# Strategy main ticks are set according to the tick in slot0, leading to incorrect allocation and loss of funds

## Description



## Proof of Concept

Forked the base chain at block 26874136 with the addresses below and add 1e18 liquidity of each token in the constructor. The swap will place the price exactly at the boundary, which means a second swap of just 1 wei is enough to push the pool to the next tick. The price is currently tick -1769, but tick -1770 is used as reference, so liquidity is allocated to ticks -1772 to -1768. A 1 wei swap moves the tick to -1769, so only 1 tick spacing has to be crossed to the right to reach the upper -1768 boundary, whereas 3 tick spacing must be crossed to the left. Thus, the position is not symmetrical and will lead to loss of fees.

The reason this happens is that the next tick to the left includes the current tick, so for example while it is at tick -1770, the next tick in the code to the left will also be -1770, having to cross 3 tick spacings to the left to reach the lower boundary, but 1 to the right only.

```solidity
    IUniswapV3Pool pool = IUniswapV3Pool(0x20E068D76f9E90b90604500B84c7e19dCB923e7e);
    IERC20 wbtc = IERC20(0x4200000000000000000000000000000000000006); // token0
    IERC20 usdc = IERC20(0xc1CBa3fCea344f92D9239c08C0568f6F2F0ee452); // token1
    address uniRouter = address(0x2626664c2603336E57B271c5C0b26F421741e481);

function test_POC_WrongTicks_DueToNotUsingSqrtPriceX96() public {
    (uint160 sqrtPriceX96, int24 tick,,,,,) = pool.slot0();
    assertEq(tick, -1769);

    //@audit swap to clear current tick token0 liquidity
    uint256 amountToSwap = 100e18;
    deal(address(wbtc), depositor, amountToSwap);
    vm.startPrank(depositor);
    IMainnetRouter.ExactInputSingleParamsV2 memory swapParams;
    swapParams.tokenIn = address(wbtc);
    swapParams.tokenOut = address(usdc);
    swapParams.recipient = depositor;
    swapParams.fee = 100;
    swapParams.amountIn = amountToSwap;
    swapParams.sqrtPriceLimitX96 = TickMath.getSqrtRatioAtTick(-1769);
    wbtc.approve(uniRouter, amountToSwap);
    IMainnetRouter(uniRouter).exactInputSingle(swapParams);

    vm.startPrank(rebalancer);
    skip(10 minutes);
    IStrategy(strategy).rebalance();

    IStrategy.Position memory mainPos = IStrategy(strategy).getMainPosition();
    (sqrtPriceX96, tick,,,,,) = pool.slot0();
    assertEq(sqrtPriceX96, TickMath.getSqrtRatioAtTick(tick + 1)); //@audit price is in tick -1769 actually
    assertEq(tick, -1770); //@audit but current tick is 1 more
    assertEq(mainPos.tickLower, -1772);
    assertEq(mainPos.tickUpper, -1768);

    //@audit swaps just 1 wei, which is enough to cross to next tick.
    //@audit thus, the position is not 50/50 symmetric.
    amountToSwap = 1;
    deal(address(usdc), depositor, amountToSwap);
    vm.startPrank(depositor);
    swapParams.tokenIn = address(usdc);
    swapParams.tokenOut = address(wbtc);
    swapParams.recipient = depositor;
    swapParams.fee = 100;
    swapParams.amountIn = amountToSwap;
    swapParams.sqrtPriceLimitX96 = 0;
    usdc.approve(uniRouter, amountToSwap);
    IMainnetRouter(uniRouter).exactInputSingle(swapParams);

    mainPos = IStrategy(strategy).getMainPosition();
    (, tick,,,,,) = pool.slot0();
    assertEq(tick, -1769); //@audit proves price moves outside range in just 1 wei swap
}
```

## Recommendation

Get the tick from the sqrtPrice and set the position ticks according to it.
