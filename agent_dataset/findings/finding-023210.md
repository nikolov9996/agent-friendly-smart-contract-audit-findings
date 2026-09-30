---
id: 23210
severity: "High"
---

# Frequency-dependent TaxCalc

## Description

```solidity
TaxCalculator.sol::calculateCompoundedFactor uses discrete formula for calculating the compounded factor. Combined with the wrong divisor (1000 instead of 10_000, as I outline in another finding), when collection's utilization factor is moderately high (e.g. 90%), and the operations with the collection happen relatively frequently (e.g. every day), this leads to charging users excessive interest rates: for this example, 3200% more than expected.
discrete formula are less severe, but still quite substantial: namely for a 100% collection utilization, depending of the frequency, either the user will be charged up to e −2 ≈71% more interest per year compared to the non-compound interest, or the protocol will receive up to 1 −1/(e −1) ≈42% less interest per year compared to the compound interest.
It's worth noting that calculateCompoundedFactor is called whenever a new checkpoint is created for the collection, which happens e.g. when any user creates a listing, cancels a listing, or fills a listing. This is neither enough to reach the desired precision, nor is it gas efficient.
Depending on the frequency of collection operations, either:
• If non-compound interest is expected, but the frequency is high, then the users will be charged up to 71% more interest than they expect;
• If compound interest is expected, but the frequency is low, then the protocol will receive up to 42% less interest than it expects.
TaxCalculator.sol::calculateCompoundedFactor employs the following formula:
compoundedFactor_ = _previousCompoundedFactor * (1e18 + (perSecondRate / 1000 * _timePeriod)) / 1e18;
,→ the compounded interest. The problem is that the formula will give vastly different results depending on the frequency of operations which have nothing to do with the user who holds the protected listing.
Internal pre-conditions
Varying frequency of collection operations.
External pre-conditions
none
Attack Path
No attack is necessary. The interest rates will be wrongly calculated in most cases.
Either users are charged up to 71% more interest than they expect, or the protocol receives up to 42% less interest than it expects.
```

## Proof of Concept

Drop this test to TaxCalculator.t.sol, and execute with forgetest --match-test test_WrongInterestCalculation
```solidity
// This test uses the unmodified source code, with the wrong divisor of 1000
function test_WrongInterestCalculation() public view {
    // We fix collection utilization to 90%
    uint utilization = 0.9 ether;
    // New checkpoints with the updated compoundedFactor are created
    // and stored whenever there is activity wrt. the collection
    // The expected interest multiplier after 1 year
    uint expectedFactor =
        taxCalculator.calculateCompoundedFactor(1 ether, utilization, 365 days);
    // The resulting interest multiplier if some activity happens every day
    uint compoundedFactor = 1 ether;
    for (uint time = 0; time < 365 days; time += 1 days) {
        compoundedFactor =
            taxCalculator.calculateCompoundedFactor(compoundedFactor, utilization,
                1 days);
        ,→
    }
    // The user loss due to the activity which doesn't concern them is 3200%
    assertApproxEqRel(
        33 ether * expectedFactor / 1 ether,
        compoundedFactor,
        0.01 ether);
}
```

## Recommendation

Variant 1: If non-compound interest is desired, apply this diff:
```diff
diff --git a/flayer/src/contracts/TaxCalculator.sol b/flayer/src/contracts/TaxCalculator.sol
index 915c0ff..4031aba 100644
--- a/flayer/src/contracts/TaxCalculator.sol
+++ b/flayer/src/contracts/TaxCalculator.sol
@@ -87,7 +87,7 @@ contract TaxCalculator is ITaxCalculator {
     uint perSecondRate = (interestRate * 1e18) / (365 * 24 * 60 * 60);
     // Calculate new compounded factor
-    compoundedFactor_ = _previousCompoundedFactor * (1e18 + (perSecondRate / 1000 * _timePeriod)) / 1e18;
+    compoundedFactor_ = _previousCompoundedFactor + (perSecondRate * _timePeriod / 1000);
}
/**
```
Variant 2: If compound interest is desired, employ either periodic per-second compounding, or continuous compounding with exponentiation. Any of these approaches are precise enough and much more gas efficient than the current one, but require substantial refactoring.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the TaxCalculator contract where the function that updates the compounded interest factor uses a discrete arithmetic expression with an incorrect scaling divisor. Instead of dividing the per‑second rate by 10,000, the code divides by 1,000, and then multiplies the result by the elapsed time period before adding it to the previous factor. Because the function is invoked each time a collection checkpoint is created – for example when a user creates, cancels or fills a listing – the interest multiplier is recomputed at a frequency that depends on marketplace activity rather than on the passage of real time. When the collection utilization is high (around 90 %) and checkpoints occur frequently (e.g., daily), the erroneous formula inflates the effective interest rate dramatically; a test case shows users can lose roughly 3200 % more than expected over a year. Conversely, if the protocol expects compound interest but checkpoints are sparse, the same mis‑scaled calculation can reduce the protocol’s earned interest by up to 42 % per year. The bug is a classic case of a financial‑logic error: an inaccurate compounding model caused by a wrong divisor and a discrete update that does not reflect continuous accrual. It manifests as users receiving higher fees than advertised, balances decreasing faster than anticipated, or refunds appearing smaller or missing. The issue is hard to notice because the contract still records a numeric interest factor, so the discrepancy only becomes apparent after prolonged operation or when comparing expected versus actual returns. No external attacker is required; the flaw is deterministic and affects every participant who interacts with the collection. The proper fix is to replace the discrete update with either a correctly scaled addition (using the proper divisor) for simple non‑compound interest, or to implement a mathematically sound compounding method such as per‑second exponentiation or continuous compounding, which also reduces gas consumption. By aligning the calculation with the intended financial model, the protocol will charge users the advertised rate and collect the expected interest, restoring trust in the system’s accounting assumptions.
