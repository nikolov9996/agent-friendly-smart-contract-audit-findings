---
id: 25103
severity: "Crit/High"
---

# Codeup::claimCodeupERC20() may be forever DoSed by creating the Uniswap pool before it is called

## Description

`Uniswap` pools may be created without the underlying tokens existence, which means that someone may do this before `Codeup::claimCodeupERC20()` is ever called, making it revert when `UniswapV2Factory::createPair()` is called as the pool has already been created.

## Proof of Concept

No PoC provided.

## Recommendation

`UniswapV2Router::addLiquidity()` creates the pool if it does not yet exist, so there is not need to directly created it. The only concern is setting the `uniswapV2Pool` variable, which may be performed for example by doing:

```solidity
if (uniswapV2Pool == address(0)) {
    uint256 maxFirstLiquidity = MAX_FIRST_LIQUIDITY_AMOUNT;
    uint256 firstLiquidity = wethBalance > maxFirstLiquidity
        ? maxFirstLiquidity
        : wethBalance;

    _addLiquidity(
        routerMemory,
        wethMemory,
        codeupERC20Memory,
        firstLiquidity,
        FIRST_LIQUIDITY_GAME_TOKEN,
        0,
        0,
        currentContract
    );

    uniswapV2Pool = IUniswapV2Factory(uniswapV2Factory).getPair(
        wethMemory,
        codeupERC20Memory
    );

    emit PoolCreated(uniswapV2Pool);
} else {
```
