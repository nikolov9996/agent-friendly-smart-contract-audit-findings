---
id: 22291
severity: "High"
---

# There are multiple issues with the decimal conversions between the vault and the strategy

## Description

```solidity
The `StrategyLeverage` contract has multiple incorrect decimal handling issues, causing the system to not support tokens with decimals other than 18.
```

## Proof of Concept

First, the vault contract’s share decimal is set to 18, as recommended by the ERC4626 standard. Ideally, the vault’s share decimal should reflect the underlying token’s decimal. Otherwise, conversions through `convertToShares` and `convertToAssets` would be required. 

In `StrategyLeverage`, we can see that all calls to `totalAssets()` are converted to 18 decimals for share calculations.

Under the above premise, the contract has multiple decimal handling errors, making it incompatible with tokens that use decimals other than 18: 

1. The `_deploy` function should return the amount in the system’s 18-decimal format, rather than the token’s native decimal format.
```solidity
function _depositInternal(uint256 assets, address receiver) private returns (uint256 shares) {
    ...
    uint256 deployedAmount = _deploy(assets);

    // Calculate shares to mint
    shares = total.toBase(deployedAmount, false);

    // Prevent inflation attack for the first deposit
    if (total.base == 0 && shares < _MINIMUM_SHARE_BALANCE) {
        revert InvalidShareBalance();
    }

    // Mint shares to the receiver
    _mint(receiver, shares);

    // Emit deposit event
    emit Deposit(msg.sender, receiver, assets, shares);
}
```
The `_deploy` function is used to calculate shares, so it should return the amount in the system’s 18-decimal format. However, the strategy always returns the amount in the token’s native decimal format. To address this, the `_pendingAmount` in the `_supplyBorrow` function should be converted to 18-decimal format.

2. In the `_redeemInternal` process, the `withdrawAmount` passed to `_undeploy` is in 18-decimal format (since `totalAssets` returns 18-decimal values).
```solidity
function _redeemInternal(
    uint256 shares,
    address receiver,
    address holder,
    bool shouldRedeemETH
) private returns (uint256 retAmount) {
    if (shares == 0) revert InvalidAmount();
    if (receiver == address(0)) revert InvalidReceiver();
    if (balanceOf(holder) < shares) revert NotEnoughBalanceToWithdraw();

    // Transfer shares to the contract if sender is not the holder
    if (msg.sender != holder) {
        if (allowance(holder, msg.sender) < shares) revert NoAllowance();
        transferFrom(holder, msg.sender, shares); 
    }

    // Calculate the amount to withdraw based on shares
    uint256 withdrawAmount = (shares * totalAssets()) / totalSupply();
    if (withdrawAmount == 0) revert NoAssetsToWithdraw();

    uint256 amount = _undeploy(withdrawAmount);
```
Therefore, in the `undeploy` process, `deltaCollateralAmount` is in 18-decimal format. It is directly packed into `data` and passed to `_repayAndWithdraw` during the callback.  

As a result, the `_withdraw` functions in `StrategyLeverageAAVEv3` and `StrategyLeverageMorphoBlue` should convert the input `amount` from 18-decimal format to the token's actual decimal format. Otherwise, the wrong amount will be withdrawn.

3. In the `_undeploy` process, `deltaDebt` and fees should be converted from 18-decimal format to the `debtToken`'s actual decimal format.

4. The `_convertToCollateral` and `_convertToDebt` functions expect the `amount` parameter to be in 18-decimal format, as required for calculations by `_toDebt` and `_toCollateral` using the oracle. However, before proceeding with the swap, the amount needs to be converted to the respective token's actual decimal format. Additionally, `_convertToCollateral` receives the token's original decimal `amount` during the deploy process, leading to incorrect calculations by the oracle.
```solidity
/**
 * @dev Internal function to convert the specified amount from Debt Token to the underlying collateral asset cbETH, wstETH, rETH.
 *
 * This function is virtual and intended to be overridden in derived contracts for customized implementation.
 *
 * @param amount The amount to convert from debtToken.
 * @return uint256 The converted amount in the underlying collateral.
 */
function _convertToCollateral(uint256 amount) internal virtual returns (uint256) {
    uint256 amountOutMinimum = 0;

    if (getMaxSlippage() > 0) {
        uint256 wsthETHAmount = _toCollateral(
            IOracle.PriceOptions({maxAge: getPriceMaxAge(), maxConf: getPriceMaxConf()}),
            amount,
            false
        );
        amountOutMinimum = (wsthETHAmount * (PERCENTAGE_PRECISION - getMaxSlippage())) / PERCENTAGE_PRECISION;
    }
    // 1. Swap Debt Token -> Collateral Token
    (, uint256 amountOut) = swap(
        ISwapHandler.SwapParams(
            _debtToken, // Asset In
            _collateralToken, // Asset Out
            ISwapHandler.SwapType.EXACT_INPUT, // Swap Mode
            amount, // Amount In
            amountOutMinimum, // Amount Out
            bytes("") // User Payload
        )
    );
    return amountOut;
}

/**
 * @dev Internal function to convert the specified amount to Debt Token from the underlying collateral.
 *
 * This function is virtual and intended to be overridden in derived contracts for customized implementation.
 *
 * @param amount The amount to convert to Debt Token.
 * @return uint256 The converted amount in Debt Token.
 */
function _convertToDebt(uint256 amount) internal virtual returns (uint256) {
    uint256 amountOutMinimum = 0;
    if (getMaxSlippage() > 0) {
        uint256 ethAmount = _toDebt(
            IOracle.PriceOptions({maxAge: getPriceMaxAge(), maxConf: getPriceMaxConf()}),
            amount,
            false
        );
        amountOutMinimum = (ethAmount * (PERCENTAGE_PRECISION - getMaxSlippage())) / PERCENTAGE_PRECISION;
    }
    // 1.Swap Colalteral -> Debt Token
    (, uint256 amountOut) = swap(
        ISwapHandler.SwapParams(
            _collateralToken, // Asset In
            _debtToken, // Asset Out
            ISwapHandler.SwapType.EXACT_INPUT, // Swap Mode
            amount, // Amount In
            amountOutMinimum, // Amount Out
            bytes("") // User Payload
        )
    );
    return amountOut;
}
```
5. The `_convertToCollateral` and `_convertToDebt` functions default to returning the `amount` in the token’s actual decimal format. However, certain parts of the code assume they return the amount in 18-decimal format, leading to potential miscalculations.
6. The `_adjustDebt` function should convert the flash loan amount from 18-decimal format to the token’s original decimal format.
7. The `_payDebt` function will receive an amount in 18-decimal format, but when performing the swap, the amount is not converted to the token’s actual decimal format. This can lead to incorrect calculations during the swap process.

## Recommendation

No recommendation

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is an incorrect handling of token decimals inside the StrategyLeverage contract and its interaction with the ERC4626 vault. The code assumes that every amount used for share calculations, debt repayment and token swaps is expressed with 18 decimals, which is the standard for Ether, but many ERC20 tokens use a different number of decimal places. Because the vault’s share decimal is fixed at 18, the strategy converts values returned by totalAssets() to 18‑decimal format but then passes amounts that are still in the token’s native decimal format to internal functions such as _deploy, _undeploy, _convertToCollateral and _convertToDebt. This mismatch causes the share‑to‑asset conversion to be off by a factor equal to 10^(18‑tokenDecimals). The root cause is the lack of explicit scaling when moving between the vault’s 18‑decimal share space and the token’s actual decimal space. An attacker or any user can exploit the bug by depositing a token with non‑18 decimals; the contract will mint an incorrect number of shares because the deployed amount is not scaled to 18 decimals. When redeeming, the contract will calculate a withdraw amount based on the wrong share value and then call _undeploy with an amount that is still in 18‑decimal format, leading to an under‑withdrawal or over‑withdrawal depending on the direction of the scaling error. The impact is that users may receive less of the underlying asset than expected, balances displayed in the UI may appear correct while the actual token balance is reduced, or in worst cases the protocol could suffer an inflation attack where extra shares are minted without corresponding assets. The bug manifests whenever the underlying token’s decimals differ from 18 – during deposit, redemption, collateral‑to‑debt swaps, flash‑loan adjustments and fee calculations. All participants that interact with the vault – token holders, liquidity providers and the protocol itself – are affected because the accounting invariants of ERC4626 (share value equals underlying asset value) are broken. The problem was discovered during a formal audit by Code4rena, where the auditors traced the flow of amounts through the strategy and observed that several functions returned or accepted values in the wrong decimal base. The issue is subtle because the contract does not emit obvious error messages; the arithmetic still succeeds, but the scaling error silently skews the accounting, making it hard to detect without inspecting the decimal conversion logic. To remediate, the contract should treat the vault’s share decimal as matching the underlying token’s decimals, or explicitly convert every amount to the 18‑decimal base before performing share calculations and back to the token’s native decimals before any external token transfer or swap. Functions such as _deploy, _undeploy, _convertToCollateral, _convertToDebt, _adjustDebt and _payDebt must include proper scaling steps, and the vault’s share decimal should be set dynamically based on the underlying token. By normalising the decimal handling across the entire strategy, the protocol will restore correct accounting, prevent loss of funds and eliminate the possibility of share inflation attacks.
