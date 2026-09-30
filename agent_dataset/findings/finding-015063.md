---
id: 15063
severity: "High"
---

# Potential swap failure in UniswapModule

## Description

During the liquidation process, all assets in a MarginAccount are converted to the baseToken (USDC), and debts in each LiquidityPool are cleared with the help of the _clearDebtsWithPools function in MarginAccount. If sufficient funds are available (MarginAccount#L294-L296), modularSwapRouter.swapOutput is used to convert USDC to the exact amount of poolToken needed to repay the liquidity pool:
File: MarginAccount.sol
```solidity
function liquidate(
    uint marginAccountID,
    address baseToken,
    address marginAccountOwner
) external onlyRole(MARGIN_TRADING_ROLE) {
    uint amountOutInUSDC = modularSwapRouter.liquidate(erc20Params, erc721Params);
    erc20ByContract[marginAccountID][baseToken] += amountOutInUSDC;
    _clearDebtsWithPools(marginAccountID, baseToken);
}
```
File: MarginAccount.sol
```solidity
function _clearDebtsWithPools(uint marginAccountID, address baseToken) private {
    // ...
    else {
        uint amountIn = modularSwapRouter.swapOutput(baseToken, availableTokenToLiquidityPool[i], poolDebt);
        erc20ByContract[marginAccountID][baseToken] -= amountIn;
    }
    ILiquidityPool(liquidityPoolAddress).repay(marginAccountID, poolDebt);
}
```
In UniswapModule, the swapOutput function prepares parameters for the swap and executes swapRouter.exactOutput. However, the parameter amountInMaximum is always set to zero. According to Uniswap's documentation, amountInMaximum should be the maximum amount of USDC that can be used to swap for the required asset. Since it's always zero, the swap will revert, failing to convert USDC into the needed poolToken:
File: UniswapModule.sol
```solidity
function swapOutput(uint amountOut) external onlyRole(MODULAR_SWAP_ROUTER_ROLE) returns(uint amountIn) {
    amountIn = getOutputPositionValue(amountOut);
    IERC20(tokenInContract).transferFrom(marginAccount, address(this), amountIn);
    swapRouter.exactOutput(params);
    IERC20(tokenOutContract).transfer(marginAccount, amountOut);
}
```
File: UniswapModule.sol
```solidity
function _preparationOutputParams(uint256 amount) private view returns(ISwapRouter.ExactOutputParams memory params) {
    params = ISwapRouter.ExactOutputParams({
        path: uniswapPath,
        recipient: address(this),
        deadline: block.timestamp,
        amountOut: amount,
        amountInMaximum: 0
    });
}
```
This misconfiguration can cause the swap to fail, potentially leaving the system unable to clear debts during liquidations.

## Proof of Concept

No poc.

## Recommendation

It is advisable to adjust the amountInMaximum in the UniswapModule::swapOutput function to reflect the actual maximum input expected for the swap. This adjustment ensures that the swap does not revert due to an insufficient input amount:
```solidity
function swapOutput(uint amountOut) external onlyRole(MODULAR_SWAP_ROUTER_ROLE) returns(uint amountIn) {
    ISwapRouter.ExactOutputParams memory params = _preparationOutputParams(amountOut);
    amountIn = getOutputPositionValue(amountOut);
    params.amountInMaximum = amountIn;
    IERC20(tokenInContract).transferFrom(marginAccount, address(this), amountIn);
    swapRouter.exactOutput(params);
    IERC20(tokenOutContract).transfer(marginAccount, amountOut);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect configuration of the Uniswap exact‑output swap used during the liquidation flow of a margin account. In the UniswapModule the function that prepares the swap parameters always sets amountInMaximum to zero, which contradicts Uniswap’s requirement that this field contain the maximum amount of the input token (USDC) that may be spent. Because the router receives a zero allowance for the input amount, the call to swapRouter.exactOutput reverts, preventing the conversion of USDC into the pool token needed to repay a liquidity pool. The root cause is a hard‑coded value that does not reflect the actual amount of USDC required for the swap, effectively making the swap impossible. An attacker or any user who triggers a liquidation can exploit this by causing the liquidation transaction to fail; the contract will be unable to clear the outstanding debt, leaving the margin account under‑collateralised and potentially locking funds in the contract. The impact is that debts remain uncleared, the protocol may suffer from unrepayed obligations, and users see their liquidation attempts revert with no change to balances. This condition occurs whenever the liquidate function calls _clearDebtsWithPools and the amount of pool token to repay is greater than zero, which is the normal case for any non‑trivial liquidation. The affected parties are margin account owners, the protocol’s risk engine, and the liquidity pools that expect repayment. The issue was discovered during a manual audit that inspected the swap preparation logic and compared it with Uniswap documentation. It can be hard to notice because the transaction simply reverts without an explicit error message about the zero maximum input, and the surrounding code does not check the return value of the swap. To remediate, the amountInMaximum field should be set to the calculated amountIn (or a safe slippage‑adjusted value) before invoking exactOutput, ensuring the router is allowed to spend the required USDC. Conceptually, this is a mis‑parameterisation of an external DEX call that leads to a swap failure, a class of bugs where incorrect limits or allowances cause a contract to be unable to perform essential token exchanges, breaking business logic such as debt repayment and causing user‑facing symptoms like “liquidation failed”, “no USDC was swapped”, or “my balance stays the same despite liquidation”.
