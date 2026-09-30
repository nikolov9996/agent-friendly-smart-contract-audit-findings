---
id: 18075
severity: "High"
---

# Basket range formula is inefficient, leading the protocol to unnecessary haircut

## Description

The `BackingManager.manageTokens()` function checks if there’s any deficit in collateral, in case there is, if there’s a surplus from another collateral token it trades it to cover the deficit, otherwise it goes for a ‘haircut’ and cuts the amount of basket ‘needed’ (i.e. the number of baskets RToken claims to hold).

In order to determine how much deficit/surplus there is the protocol calculates the ‘basket range’, where the top range is the optimistic estimation of the number of baskets the token would hold after trading and the bottom range is a pessimistic estimation.

The estimation is done by dividing the total collateral value by the price of 1 basket unit (for optimistic estimation the max value is divided by min price of basket-unit and vice versa).

The problem is that this estimation is inefficient, for cases where just a little bit of collateral is missing the range ‘band’ (range.top - range.bottom) would be about 4% (when oracle error deviation is ±1%) instead of less than 1%.

This can cause the protocol an unnecessary haircut of a few percent where the deficit can be solved by simple trading.

This would also cause the price of `RTokenAsset` to deviate more than necessary before the haircut.

## Proof of Concept

In the following PoC, the basket changed so that it has 99% of the required collateral for 3 tokens and 95% for the 4th.

The basket range should be 98±0.03% (the basket has 95% collateral + 4% of 3/4 tokens. That 4% is worth 3±0.03% if we account for oracle error of their prices), but in reality the protocol calculates it as ~97.9±2%.

That range causes the protocol to avoid trading and go to an unnecessary haircut to ~95%

```solidity
diff --git a/contracts/plugins/assets/RTokenAsset.sol b/contracts/plugins/assets/RTokenAsset.sol
index 62223442..03d3c3f4 100644
--- a/contracts/plugins/assets/RTokenAsset.sol
+++ b/contracts/plugins/assets/RTokenAsset.sol
@@ -123,7 +123,7 @@ contract RTokenAsset is IAsset {
     // ==== Private ====

     function basketRange()
-        private
+        public
         view
         returns (RecollateralizationLibP1.BasketRange memory range)
     {
diff --git a/test/Recollateralization.test.ts b/test/Recollateralization.test.ts
index 3c53fa30..386c0673 100644
--- a/test/Recollateralization.test.ts
+++ b/test/Recollateralization.test.ts
@@ -234,7 +234,42 @@ describe(`Recollateralization - P${IMPLEMENTATION}`, () => {
         // Issue rTokens
         await rToken.connect(addr1)['issue(uint256)'](issueAmount)
       })
+      it('PoC basket range', async () => {
+        let range = await rTokenAsset.basketRange();
+        let basketTokens = await basketHandler.basketTokens();
+        console.log({range}, {basketTokens});
+        // Change the basket so that current balance would be 99 or 95 percent of
+        // the new basket
+        let q99PercentLess = 0.25 / 0.99;
+        let q95ercentLess = 0.25 / 0.95;
+        await basketHandler.connect(owner).setPrimeBasket(basketTokens, [fp(q99PercentLess),fp(q99PercentLess), fp(q95ercentLess), fp(q99PercentLess)])
+        await expect(basketHandler.connect(owner).refreshBasket())
+        .to.emit(basketHandler, 'BasketSet')
+
+        expect(await basketHandler.status()).to.equal(CollateralStatus.SOUND)
+        expect(await basketHandler.fullyCollateralized()).to.equal(false)
+
+        range = await rTokenAsset.basketRange();
+
+        // show the basket range is 95.9 to 99.9
+        console.log({range});

+        let needed = await rToken.basketsNeeded();

+        // show that prices are more or less the same
+        let prices = await Promise.all( basket.map(x => x.price()));

+        // Protocol would do a haircut even though it can easily do a trade
+        await backingManager.manageTokens([]);
+
+        // show how many baskets are left after the haircut
+         needed = await rToken.basketsNeeded();
+         
+        console.log({prices, needed});
+        return;
+    
+      })
+      return;
       it('Should select backup config correctly - Single backup token', async () => {
         // Register Collateral
         await assetRegistry.connect(owner).register(backupCollateral1.address)
@@ -602,7 +637,7 @@ describe(`Recollateralization - P${IMPLEMENTATION}`, () => {
         expect(quotes).to.eql([initialQuotes[0], initialQuotes[1], initialQuotes[3], bn('0.25e18')])
       })
-
+    return;
     context('With multiple targets', function () {
       let issueAmount: BigNumber
       let newEURCollateral: FiatCollateral
@@ -785,7 +820,7 @@ describe(`Recollateralization - P${IMPLEMENTATION}`, () => {
       })
     })
   })

+  return;
   describe('Recollateralization', function () {
     context('With very simple Basket - Single stablecoin', function () {
       let issueAmount: BigNumber
```

Output (comments are added by me):

```solidity
{
  range: [
    top: BigNumber { value: "99947916501440267201" },  //  99.9 basket units
    bottom: BigNumber { value: "95969983506382791000" } // 95.9 basket units
  ]
}
{
  prices: [
    [
      BigNumber { value: "990000000000000000" },
      BigNumber { value: "1010000000000000000" }
    ],
    [
      BigNumber { value: "990000000000000000" },
      BigNumber { value: "1010000000000000000" }
    ],
    [
      BigNumber { value: "990000000000000000" },
      BigNumber { value: "1010000000000000000" }
    ],
    [
      BigNumber { value: "19800000000000000" },
      BigNumber { value: "20200000000000000" }
    ]
  ],
  needed: BigNumber { value: "94999999905000000094" } // basket units after haircut: 94.9
}
```

## Recommendation

Change the formula so that we first calculate the ‘base’ (i.e. the min amount of baskets the RToken can satisfy without trading):

```solidity
base = basketsHeldBy(backingManager) // in the PoC's case it'd be 95
(diffLowValue, diffHighValue) = (0,0) 
for each collateral token:
    diff = collateralBalance - basketHandler.quantity(base) 
    (diffLowValue, diffHighValue) = diff * (priceLow, priceHigh)
addBasketsLow = diffLowValue / basketPriceHigh
addBasketHigh = diffHighValue / basketPriceLow
range.top = base + addBasketHigh
range.bottom = base + addBasketLow
```

Would like sponsor to comment on this issue and will determine severity from there.

Agree this behaves the way described. We’re aware of this problem and have been looking at fixes that are similar to the one suggested.

Thank you @tbrent - I think High seems correct here as this does directly lead to a loss of value for users.

@0xean - Seems right.

This PR simplifies and improves the basket range formula. The new logic should provide much tighter basket range estimates and result in smaller haircuts. [reserve-protocol/protocol#585](https://github.com/reserve-protocol/protocol/pull/585)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inefficient calculation of the basket range used by the BackingManager to decide whether a collateral deficit can be covered by trading surplus assets or whether a haircut must be applied. The protocol estimates the optimistic (top) and pessimistic (bottom) number of basket units by dividing the total collateral value by the extreme price bounds of the basket‑unit – the maximum value is divided by the minimum price and the minimum value by the maximum price. When oracle price error is limited to ±1 %, this method creates a range band that can be as wide as four percent even if the actual shortfall is only a fraction of a percent. Because the range appears larger than the true deficit, the contract concludes that the deficit cannot be remedied by simple trades and proceeds to cut the number of baskets the RToken claims to hold – a process known as a haircut. This over‑estimation can be triggered whenever the system has a small collateral shortfall combined with normal oracle variance, which is a common state during normal operation. Token holders are the primary victims: they expect the protocol to trade surplus collateral to maintain full backing, but instead see the RToken price deviate downward and receive fewer redemption units, effectively losing value. The issue was discovered during a Code4rena audit where a proof‑of‑concept test showed that the calculated basket range was ~97.9 ± 2 % instead of the expected ~98 ± 0.03 %, leading the protocol to execute an unnecessary haircut that reduced the basket to about 95 % of its required value. The bug is subtle because the percentage differences are small and the haircut occurs automatically without an explicit error flag, making it easy to overlook in routine monitoring. Conceptually, the fix is to first compute the minimum number of baskets that can be satisfied without any trades (the base) and then add the surplus value using low and high price bounds, resulting in a much tighter top and bottom estimate. This re‑structures the formula to avoid the overly conservative bounds that cause the wide range. In broader terms, the problem belongs to the class of financial state mis‑estimation bugs where extreme price bounds are applied symmetrically, leading to unnecessary loss of collateral value. From a user’s perspective, the protocol appears to “lose funds” or “cut the refund” – the expected redemption amount is lower than anticipated, and the token price may drop more than justified by market conditions. The attack scenario can be described step‑by‑step: (1) a small collateral deficit arises; (2) the oracle reports prices within its normal error margin; (3) the basket range calculation inflates the perceived deficit because of the max/min price division; (4) the BackingManager decides the deficit cannot be covered by trading; (5) it triggers a haircut, reducing the claimed basket units; (6) token holders receive fewer RToken units or see the token price fall, resulting in a loss of value that could have been avoided with a correct range calculation.
