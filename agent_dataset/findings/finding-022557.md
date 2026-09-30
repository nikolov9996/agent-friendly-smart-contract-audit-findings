---
id: 22557
severity: "Medium"
---

# Not considering fees when wrapping mtOFTs

## Description

When wrapping mtOFTs in leverage executors, fees are not considered, making calls always revert because the obtained assets amount is always smaller than expected. Tapioca will allow tOFTs and mtOFTs to act as collateral in some of Tapioca’s markets, as described by the documentation. Although regular tOFTs don’t hardcode fees to 0, meta-tOFTs (mtOFTs) could incur a fee when wrapping, as shown in the following code snippet, where _checkAndExtractFees() is used to calculate a fee considering the wrapped _amount:
```solidity
// mTOFT.sol
function wrap(address _fromAddress, address _toAddress, uint256 _amount)
external
payable
whenNotPaused
nonReentrant
returns (uint256 minted)
{
    ...
    uint256 feeAmount = _checkAndExtractFees(_amount);
    if (erc20 == address(0)) {
        _wrapNative(_toAddress, _amount, feeAmount);
    } else {
        if (msg.value > 0) revert mTOFT_NotNative();
        _wrap(_fromAddress, _toAddress, _amount, feeAmount);
    }
    return _amount - feeAmount;
}
```
When fees are applied, the amount of mtOFTs minted to the caller won’t be the full _amount, but the _amount - feeAmount. Tapioca’s leverage executors are required to wrap/unwrap assets when tOFTs are used as collateral in order to properly perform their logic. The problem is that leverage executors don’t consider the fact that if collateral is an mtOFT, then a fee could be applied. Let’s consider the BaseLeverageExecutor contract (who has the _swapAndTransferToSender() function, called by all leverage executors):
```solidity
// BaseLeverageExecutor.sol
function _swapAndTransferToSender(
    bool sendBack,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    bytes memory data
) internal returns (uint256 amountOut) {
    SLeverageSwapData memory swapData = abi.decode(data, (SLeverageSwapData));
    ...
    // If the tokenOut is a tOFT, wrap it. Handles ETH and ERC20.
    // If `sendBack` is true, wrap the `amountOut to` the sender. else, wrap it to this contract.
    if (swapData.toftInfo.isTokenOutToft) {
        _handleToftWrapToSender(sendBack, tokenOut, amountOut);
    } else if (sendBack == true) {
        // If the token wasn't sent by the wrap OP, send it as a transfer.
        IERC20(tokenOut).safeTransfer(msg.sender, amountOut);
    }
}
```
As we can see in the code snippet, if the user requires to wrap the obtained swapped assets by setting swapData.toftInfo.isTokenOutToft to true, then the internal _handleToftWrapToSender() function will be called. This function will wrap the tOFT (or mtOFT) and send it to msg.sender or address(this), depending on the user’s sendBack input:
```solidity
// BaseLeverageExecutor.sol
function _handleToftWrapToSender(bool sendBack, address tokenOut, uint256 amountOut) internal {
    address toftErc20 = ITOFT(tokenOut).erc20();
    address wrapsTo = sendBack == true ? msg.sender : address(this);
    if (toftErc20 == address(0)) {
        // If the tOFT is for ETH, withdraw from WETH and wrap it.
        weth.withdraw(amountOut);
        ITOFT(tokenOut).wrap{value: amountOut}(address(this), wrapsTo, amountOut);
    } else {
        // If the tOFT is for an ERC20, wrap it.
        toftErc20.safeApprove(tokenOut, amountOut);
        ITOFT(tokenOut).wrap(address(this), wrapsTo, amountOut);
        toftErc20.safeApprove(tokenOut, 0);
    }
}
```
The problem here is that if tokenOut is an mtOFT, then a fee might be applied when wrapping. However, this function does not consider the wrap() function return minted amount, which is always _amount - feeAmount. This leads to a vulnerability where contracts performing this wraps will believe they have more funds than the intended, leading to a Denial of Service and making the leverage executors never work with mtOFTs. High. The core functionality of leverage won’t work if the tokens are mtOFT tokens.

## Proof of Concept

Let’s say a user wants to lever up by calling BBLeverage.sol's buyCollateral() function:
```solidity
// BBLeverage.sol
function buyCollateral(address from, uint256 borrowAmount, uint256 supplyAmount, bytes calldata data)
external
optionNotPaused(PauseType.LeverageBuy)
solvent(from, false)
notSelf(from)
returns (uint256 amountOut)
{
    ...
    {
        amountOut = leverageExecutor.getCollateral(
            collateralId,
            address(asset),
            address(collateral),
            memoryData.supplyShareToAmount + memoryData.borrowShareToAmount,
            calldata_.from,
            calldata_.data
        );
    }
    uint256 collateralShare = yieldBox.toShare(collateralId, amountOut, false);
    address(asset).safeApprove(address(yieldBox), type(uint256).max);
    yieldBox.depositAsset(collateralId, address(this), address(this), 0, collateralShare);
    address(asset).safeApprove(address(yieldBox), 0);
    ...
}
```
1. As we can see, the contract will call leverageExecutor.getCollateral() in order to perform the swap. Notice how the value returned by getCollateral() will be stored in the amountOut variable, which will later be converted to collateralShare and deposited into the yieldBox.
2. Let’s say the leverageExecutor in this case is the SimpleLeverageExecutor.sol contract. When getCollateral() is called, SimpleLeverageExecutor will directly return the value returned by the internal _swapAndTransferToSender() function:
```solidity
// SimpleLeverageExecutor.sol
function getCollateral(
    address assetAddress,
    address collateralAddress,
    uint256 assetAmountIn,
    bytes calldata swapperData
) external payable override returns (uint256 collateralAmountOut) {
    // Should be called only by approved SGL/BB markets.
    if (!cluster.isWhitelisted(0, msg.sender)) revert SenderNotValid();
    return _swapAndTransferToSender(true, assetAddress, collateralAddress, assetAmountIn, swapperData);
}
```
swapped and wrapped, and will instead only return the amount obtained when swapping, assuming that wraps will always mint the same amount:
```solidity
// BaseLeverageExecutor.sol
function _swapAndTransferToSender(
    bool sendBack,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    bytes memory data
) internal returns (uint256 amountOut) {
    ...
    amountOut = swapper.swap(swapperData, amountIn, swapData.minAmountOut);
    ...
    if (swapData.toftInfo.isTokenOutToft) {
        _handleToftWrapToSender(sendBack, tokenOut, amountOut);
    } else if (sendBack == true) {
        // If the token wasn't sent by the wrap OP, send it as a transfer.
        IERC20(tokenOut).safeTransfer(msg.sender, amountOut);
    }
}
```
If the tokenOut is an mtOFT, the actual obtained amount will be smaller than the amountOut stored due to the fees that might be applied. This makes the yieldBox.depositAsset() in BBLeverage.sol inevitably always fail due to not having enough funds to deposit into the YieldBox effectively causing a Denial of Service.

## Recommendation

Consider the fees applied when wrapping assets by following OFT’s API, and store the returned value by wrap(). For example, _handleToftWrapToSender() could return an integer with the actual amount obtained after wrapping:
```solidity
// BaseLeverageExecutor.sol
function _handleToftWrapToSender(bool sendBack, address tokenOut, uint256 amountOut) internal returns(uint256 _amountOut) {
    address toftErc20 = ITOFT(tokenOut).erc20();
    address wrapsTo = sendBack == true ? msg.sender : address(this);
    if (toftErc20 == address(0)) {
        // If the tOFT is for ETH, withdraw from WETH and wrap it.
        weth.withdraw(amountOut);
        _amountOut = ITOFT(tokenOut).wrap{value: amountOut}(address(this), wrapsTo, amountOut);
    } else {
        // If the tOFT is for an ERC20, wrap it.
        toftErc20.safeApprove(tokenOut, amountOut);
        _amountOut = ITOFT(tokenOut).wrap(address(this), wrapsTo, amountOut);
        toftErc20.safeApprove(tokenOut, 0);
    }
}
```
And this value should be the one stored in _swapAndTransferToSender()'s amountOut:
```solidity
function _swapAndTransferToSender(
    bool sendBack,
    address tokenIn,
    address tokenOut,
    uint256 amountIn,
    bytes memory data
) internal returns (uint256 amountOut) {
    SLeverageSwapData memory swapData = abi.decode(data, (SLeverageSwapData));
    ...
    // If the tokenOut is a tOFT, wrap it. Handles ETH and ERC20.
    // If `sendBack` is true, wrap the `amountOut to` the sender. else, wrap it to this contract.
    if (swapData.toftInfo.isTokenOutToft) {
        amountOut = _handleToftWrapToSender(sendBack, tokenOut, amountOut);
    } else if (sendBack == true) {
        // If the token wasn't sent by the wrap OP, send it as a transfer.
        IERC20(tokenOut).safeTransfer(msg.sender, amountOut);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑handling omission that occurs when meta‑tOFT (mtOFT) tokens are wrapped inside Tapioca’s leverage executors. mtOFT contracts charge a wrapping fee and return the minted amount as _amount‑feeAmount, but the BaseLeverageExecutor._handleToftWrapToSender function ignores the return value and assumes the wrapped amount equals the input amountOut. Consequently, the surrounding logic records a higher balance than actually received. This mismatch is triggered whenever a leverage executor requests a wrap of an mtOFT token – for example during a swap‑and‑transfer operation in _swapAndTransferToSender – and it happens under normal market conditions where fees are non‑zero. The affected parties are users who supply mtOFTs as collateral, the protocol’s leverage markets, and any contracts that rely on the reported amountOut to deposit assets into the YieldBox. The impact is that the reported collateral amount is overstated, causing subsequent deposit calls to fail due to insufficient token balance, which effectively results in a denial‑of‑service for any operation involving mtOFT collateral. The issue was discovered during a manual audit of the leverage executor code when the auditor noticed that the wrap() call’s return value was never captured. It is hard to notice because the wrap transaction itself succeeds and the fee is deducted silently, so the failure only appears later when the protocol attempts to move more tokens than are actually owned. The bug belongs to the class of accounting or fee‑miscalculation errors where business logic assumes a 1:1 token conversion. From a user’s perspective the UI may show that the supplied amount was accepted, but the transaction reverts and the user receives no collateral, or the balance appears to drop to zero after the operation. The expected behavior is that the amount returned by wrap() (the net amount after fees) should be used for all subsequent calculations. The proper fix is to capture the wrap() return value, propagate it back to the caller, and replace the previously stored amountOut with the net amount, ensuring that fee deductions are accounted for throughout the execution flow.
