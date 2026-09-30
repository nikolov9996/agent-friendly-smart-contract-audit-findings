---
id: 19784
severity: "High"
---

# PerpDespository#reblance and rebalanceLite

## Description

PerpDespository#reblance and rebalanceLite allows anyone to specify the account that pays the quote token. These functions allow a malicious user to abuse any allowance provided to PerpDirectory. rebalance is the worst of the two because the malicious user could sandwich attack the rebalance to steal all the funds and force the unsuspecting user to pay the shortfall.
```solidity
function rebalance(
    uint256 amount,
    uint256 amountOutMinimum,
    uint160 sqrtPriceLimitX96,
    uint24 swapPoolFee,
    int8 polarity,
) external nonReentrant returns (uint256, uint256) {
    if (polarity == -1) {
        return
            _rebalanceNegativePnlWithSwap(
                amount,
                amountOutMinimum,
                sqrtPriceLimitX96,
                swapPoolFee,
            );
    } else if (polarity == 1) {
        // disable rebalancing positive PnL
        revert PositivePnlRebalanceDisabled(msg.sender);
        // return _rebalancePositivePnlWithSwap(amount, amountOutMinimum,
        // sqrtPriceLimitX96, swapPoolFee, account);
    } else {
        revert InvalidRebalance(polarity);
    }
}
```
rebalance is an unpermissioned function that allows anyone to call and rebalance the PNL of the depository. It allows the caller to specify the an account that passes directly through to _rebalanceNegativePnlWithSwap
```solidity
function _rebalanceNegativePnlWithSwap(
    uint256 amount,
    uint256 amountOutMinimum,
    uint160 sqrtPriceLimitX96,
    uint24 swapPoolFee,
    address account
) private returns (uint256, uint256) {
    ...
    SwapParams memory params = SwapParams({
        tokenIn: assetToken,
        tokenOut: quoteToken,
        amountIn: baseAmount,
        amountOutMinimum: amountOutMinimum,
        sqrtPriceLimitX96: sqrtPriceLimitX96,
        poolFee: swapPoolFee
    });
    int256 shortFall = int256(
    if (shortFall > 0) {
        IERC20(quoteToken).transferFrom(
            account,
            address(this),
            uint256(shortFall)
        );
    } else if (shortFall < 0) {
        ...
    }
}
```
_rebalanceNegativePnlWithSwap uses both user specified swap parameters and takes the shortfall from the account specified by the user. This is where the function can be abused to steal funds from any user that sets an allowance this contract. A malicious user can sandwich attack the swap and specify malicious swap parameters to allow them to steal the entire rebalance. This creates a large shortfall which will be taken from the account that they specify, effectively stealing the funds from the user.
Example: Any account that gives the depository allowance can be stolen from. Imagine the following scenario. The multisig is going to rebalance the contract for 15000 USDC worth of ETH and based on current market conditions they are estimating that there will be a 1000 USDC shortfall because of the difference between the perpetual and spot prices (divergences between spot and perpetual price are common in trending markets). They first approve the depository for 1000 USDC. A malicious user sees this approval and immediately submits a transaction of their own. They request to rebalance only 1000 USDC worth of ETH and sandwich attack the swap to steal the rebalance. They specify the multisig as account and force it to pay the 1000 USDC shortfall and burn their entire allowance, stealing the USDC.
Anyone that gives the depository allowance can easily have their entire allowance stolen

## Proof of Concept

no poc

## Recommendation

PerpDespository#reblance and rebalanceLite should use msg.sender instead of account:
```solidity
function rebalance(
    uint256 amount,
    uint256 amountOutMinimum,
    uint160 sqrtPriceLimitX96,
    uint24 swapPoolFee,
    int8 polarity,
    address account
) external nonReentrant returns (uint256, uint256) {
    if (polarity == -1) {
        return
            _rebalanceNegativePnlWithSwap(
                amount,
                amountOutMinimum,
                sqrtPriceLimitX96,
                swapPoolFee,
                account
            );
    } else if (polarity == 1) {
        // disable rebalancing positive PnL
        revert PositivePnlRebalanceDisabled(msg.sender);
        // return _rebalancePositivePnlWithSwap(amount, amountOutMinimum,
        // sqrtPriceLimitX96, swapPoolFee, account);
    } else {
        revert InvalidRebalance(polarity);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract exposes an unpermissioned function that rebalances the perpetual depository by swapping assets and then settling any quote‑token shortfall. The caller can pass an arbitrary address that is used as the source of the shortfall repayment. Internally the function builds a swap request with user‑controlled parameters (amount, minimum output, price limit and pool fee) and, after the swap, calculates a shortfall. If the shortfall is positive the contract calls transferFrom on the quote token, pulling the required amount from the address supplied by the caller. Because the function has no access control and the account argument is not validated, a malicious actor can invoke the function with a victim’s address that has previously granted an allowance to the depository. By crafting hostile swap parameters and front‑running (sandwiching) the legitimate rebalance transaction, the attacker can inflate the shortfall to the full allowance amount and force the victim to transfer all approved tokens to the contract, effectively stealing the funds. This vulnerability manifests whenever any user approves the depository to spend their quote token, which is a normal operation for many perpetual protocols. The impact is a loss of the approved balance, leaving the victim with a zero or reduced token balance and no receipt of the expected rebalance outcome. The issue was discovered during a security audit that examined the rebalancing logic and noticed that the account parameter was passed unchecked to transferFrom. It is subtle because the function’s purpose is to correct PnL, so developers may assume that only the contract itself should be affected, overlooking that an external caller can dictate who pays the shortfall. The bug belongs to the class of “unrestricted external account parameter leading to unauthorized token transfer” and violates the accounting assumption that only the contract’s own funds are used to settle rebalancing. To remediate, the contract should replace the user‑supplied account with msg.sender, enforce that only authorized roles (e.g., the protocol’s treasury or a designated keeper) can call the function, and remove the ability to specify an arbitrary payer. Adding proper access control and ensuring that transferFrom is only invoked against the caller’s own allowance will prevent the shortfall from being charged to an unsuspecting third party and restore the intended economic safety of the rebalancing process.
