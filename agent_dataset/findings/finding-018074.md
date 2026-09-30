---
id: 18074
severity: "High"
---

# Adversary can abuse a quirk of compound redemption to manipulate the underlying exchange rate and maliciously disable cToken collaterals

## Description

Adversary can maliciously disable cToken collateral to cause loss to rToken during restructuring.

## Proof of Concept

```solidity
if (referencePrice < prevReferencePrice) {
    markStatus(CollateralStatus.DISABLED);
}
```

CTokenNonFiatCollateral and CTokenFiatCollateral both use the default refresh behavior presented in FiatCollateral which has the above lines which automatically disables the collateral if the reference price ever decreases. This makes the assumption that cToken exchange rates never decrease but this is an incorrect assumption and can be exploited by an attacker to maliciously disable a cToken being used as collateral.

[CToken.sol](https://github.com/compound-finance/compound-protocol/blob/a3214f67b73310d547e00fc578e8355911c9d376/contracts/CToken.sol#L480-L505)

```solidity
uint redeemTokens;
uint redeemAmount;
/* If redeemTokensIn > 0: */
if (redeemTokensIn > 0) {
    /*
     * We calculate the exchange rate and the amount of underlying to be redeemed:
     *  redeemTokens = redeemTokensIn
     *  redeemAmount = redeemTokensIn x exchangeRateCurrent
     */
    redeemTokens = redeemTokensIn;
    redeemAmount = mul_ScalarTruncate(exchangeRate, redeemTokensIn);
} else {
    /*
     * We get the current exchange rate and calculate the amount to be redeemed:
     *  redeemTokens = redeemAmountIn / exchangeRate
     *  redeemAmount = redeemAmountIn
     */

    // @audit redeemTokens rounds in favor of the user

    redeemTokens = div_(redeemAmountIn, exchangeRate);
    redeemAmount = redeemAmountIn;
}
```

The exchange rate can be manipulated by a tiny amount during the redeem process. The focus above is the scenario where the user requests a specific amount of underlying. When calculating the number of cTokens to redeem for a specific amount of underlying it rounds IN FAVOR of the user. This allows the user to redeem more underlying than the exchange rate would otherwise imply. Because the user can redeem _slightly_ more than intended they can create a scenario in which the exchange rate actually drops after they redeem. This is because compound calculates the exchange rate dynamically using the current supply of cTokens and the assets under management.

[CToken.sol](https://github.com/compound-finance/compound-protocol/blob/a3214f67b73310d547e00fc578e8355911c9d376/contracts/CToken.sol#L293-L312)

```solidity
function exchangeRateStoredInternal() virtual internal view returns (uint) {
    uint _totalSupply = totalSupply;
    if (_totalSupply == 0) {
        /*
         * If there are no tokens minted:
         *  exchangeRate = initialExchangeRate
         */
        return initialExchangeRateMantissa;
    } else {
        /*
         * Otherwise:
         *  exchangeRate = (totalCash + totalBorrows - totalReserves) / totalSupply
         */
        uint totalCash = getCashPrior();
        uint cashPlusBorrowsMinusReserves = totalCash + totalBorrows - totalReserves;
        uint exchangeRate = cashPlusBorrowsMinusReserves * expScale / _totalSupply;

        return exchangeRate;
    }
}
```

The exchangeRate when _totalSupply != 0 is basically:

```solidity
exchangeRate = netAssets * 1e18 / totalSupply
```

Using this formula for we can now walk through an example of how this can be exploited.

Example:

cTokens always start at a whole token ratio of 50:1 so let’s assume this ratio to begin with. Let’s use values similar to the current supply of cETH which is ~15M cETH and ~300k ETH. We’ll start by calculating the current ratio:

```solidity
exchangeRate = 300_000 * 1e18 * 1e18 / 15_000_000 * 1e8 = 2e26
```

Now to exploit the ratio we request to redeem 99e8 redeemAmount which we can use to calculate the amount of tokens we need to burn:

```solidity
redeemAmount = 99e8 * 1e18 / 2e26 = 1.98 -> 1
```

After truncation the amount burned is only 1. Now we can recalculate our ratio:

```solidity
exchangeRate = ((300_000 * 1e18 * 1e18) - 99e8) / ((15_000_000 * 1e8) - 1) = 199999999999999933333333333
```

The ratio has now been slightly decreased. In CTokenFiatCollateral the exchange rate is truncated to 18 dp so:

```solidity
(referencePrice < prevReferencePrice) -> (19999999999999993 <  2e18) == true
```

This results in that the collateral is now disabled. This forces the vault to liquidate their holdings to convert to a backup asset. This will almost certainly incur losses to the protocol that were maliciously inflicted.

The path to exploit is relatively straightforward:

`refresh()` cToken collateral to store current rate -> Manipulate compound rate via redemption -> `refresh()` cToken collateral to disable

## Recommendation

Since the issue is with the underlying compound contracts, nothing can make the attack impossible but it can be made sufficiently difficult. The simplest deterrent would be to implement a rate error value (i.e. 100) so that the exchange rate has to drop more than that before the token is disabled. The recommended value for this is a bit more complicated to unpack. The amount that the exchange rate changes heavily depends on the number of cTokens minted. The larger the amount the less it changes. Additionally a malicious user can make consecutive redemptions to lower the rate even further. Using an error rate of 1e12 would make it nearly impossible for this to be exploited while still being very sensitive to real (and concerning) changes in exchange rate.

```solidity
-   if (referencePrice < prevReferencePrice) {
+   if (referencePrice < prevReferencePrice - rateError) {
    markStatus(CollateralStatus.DISABLED);
}
```

I do see in the cToken code base that the warden is correct with regard to the round down mechanism when redeeming cTokens using a redeemAmountIn.

The question I think comes down to is this dust amount enough to counteract the interest that would be accrued to the cToken which is added during the refresh call in `CTokenFiatCollateral`

Will leave open for sponsor review.

Issue confirmed.

Many defi protocols may have similar issues. We may choose to mitigate by building in revenue hiding to something like 1 part in 1 million to all collateral plugins.

This PR adds universal revenue hiding to all appreciating collateral: [reserve-protocol/protocol#620](https://github.com/reserve-protocol/protocol/pull/620)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is a logical flaw in the way a protocol treats Compound cToken collateral during its periodic refresh. The refresh routine stores the current exchange rate of the cToken (the reference price) and automatically disables the collateral if the newly observed rate is lower than the previously stored value. This logic assumes that the cToken exchange rate never decreases, an assumption that is violated by Compound’s redemption function. When a user redeems a specific amount of underlying assets, the contract calculates the number of cTokens to burn by dividing the requested amount by the current exchange rate and truncates the result, which rounds in favor of the user. Because the rounding can cause the user to receive slightly more underlying than the exact proportional value, the total cash held by the cToken contract is reduced by a tiny amount while the total supply of cTokens is reduced by an even smaller integer amount. The net effect is a marginal decrease in the stored exchange rate after the redemption. If an attacker repeatedly performs such redemptions, the exchange rate can be nudged below the previously recorded reference price. When the next refresh runs, the condition referencePrice < prevReferencePrice evaluates to true and the collateral status is set to DISABLED. The protocol then treats the cToken as unusable collateral, forcing vaults that rely on it to liquidate their positions into a backup asset, which typically incurs a loss. The vulnerability can be exploited by any actor who can call the redeem function with a small underlying amount, repeat the operation, and trigger the refresh after each step. It affects protocols that accept cTokens as collateral, their users, and the overall funds locked in the system because the collateral may become disabled unexpectedly. The flaw was discovered during a security audit that examined the refresh logic of CTokenFiatCollateral and CTokenNonFiatCollateral and traced the rounding behavior in Compound’s CToken contract. The problem is subtle because the exchange‑rate drop is extremely small—often only a few wei—making it hard to notice in normal operation, and the disabling condition is triggered only when the rate falls, a scenario that rarely occurs under honest usage. To mitigate the issue, the refresh logic should incorporate a tolerance margin (rateError) before marking the collateral as disabled, or employ a revenue‑hiding mechanism that ignores minute fluctuations, thereby preventing an attacker from disabling the collateral through tiny, repeated redemptions. In essence, the bug belongs to the class of “exchange‑rate‑based collateral disable” vulnerabilities, where an assumption about monotonicity of a price feed is broken by rounding errors, leading to unintended collateral deactivation and potential financial loss.
