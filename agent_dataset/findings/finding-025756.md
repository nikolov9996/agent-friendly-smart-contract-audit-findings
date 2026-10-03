---
id: 25756
severity: "Medium"
---

# Strategy main ticks are not symmetric when the tick spacing is one due to incorrect isLowerSided inequality

## Description



## Proof of Concept

```solidity
    // in setup
    IUniswapV3Pool pool = IUniswapV3Pool(0x20E068D76f9E90b90604500B84c7e19dCB923e7e);
    IERC20 wbtc = IERC20(0x4200000000000000000000000000000000000006); // token0
    IERC20 usdc = IERC20(0xc1CBa3fCea344f92D9239c08C0568f6F2F0ee452); // token1
    address uniRouter = address(0x2626664c2603336E57B271c5C0b26F421741e481);
    vm.createSelectFork(vm.envString("RPC_URL_BASE"), 26874136);

function test_POC_WrongTicks_DueToIsLowerSide() public {
    skip(10 minutes);
    vm.startPrank(rebalancer);
    IStrategy(strategy).rebalance();

    IStrategy.Position memory mainPos = IStrategy(strategy).getMainPosition();
    (, int24 tick,,,,,) = pool.slot0();
    //@audit position is not symmetric, harming long term fees
    assertEq(tick, -1769);
    assertEq(mainPos.tickLower, -1770);
    assertEq(mainPos.tickUpper, -1766);
}
```

## Recommendation

`bool isLowerSided = modulo <= (tickSpacing / 2);`
