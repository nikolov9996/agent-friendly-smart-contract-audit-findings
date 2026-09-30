---
id: 5077
severity: "High"
---

# getLastMarketState does not update the market properly

## Description

getLastMarketState is used in:
• previewLendRateAfterDeposit
• getMarket
• getMaxBorrowableAmount
• getPositionLTV
• getPositionInterest

In all these endpoints except previewLendRateAfterDeposit the input parameter lendAssets supplied is 0. For those cases the calculations are almost correct, but since previewLendRateAfterDeposit provides a potentially non-zero value for lendAssets the calculation is not performed correctly.

previewLendRateAfterDeposit is supposed to:
1. First simulate the effect of accruing interest then...
2. Simulate the effect of calling lend on the specified market.

But in the current implementation these orders are not followed but instead accruing interest is performed after lending and also the lendAssets is not added to the market.totalLendAssets. This will make previewLendRateAfterDeposit to return an incorrect rate which will effect the rate returned by WrappedVault.previewRateAfterDeposit:

```solidity
if (reward == address(DEPOSIT_ASSET)) {
    uint256 dahliaRate = dahlia.previewLendRateAfterDeposit(marketId, assets);
    rewardsRate += dahliaRate;
}
```

and thus affect the following inequality checked in VaultMarketHub.allocateOffer:

```solidity
if (offer.incentivesRatesRequested[i] > WrappedVault(offer.targetVault).previewRateAfterDeposit(offer.incentivesRequested[i], fillAmount)) {
    revert OfferConditionsNotMet();
}
```

## Proof of Concept

no poc

## Recommendation

Apply the following changes:

```diff
diff --git a/src/core/impl/InterestImpl.sol b/src/core/impl/InterestImpl.sol
index f672414..2ef20b9 100644
--- a/src/core/impl/InterestImpl.sol
+++ b/src/core/impl/InterestImpl.sol
@@ -75,29 +75,40 @@ library InterestImpl {
    feeShares = (interestEarnedAssets * feeRate * totalLendShares) / (Constants.FEE_PRECISION * (totalLendAssets + interestEarnedAssets));
}
-
/// @notice Gets the expected market balances after interest accrual.
+
/// @notice Gets the expected market balances after interest accrual and lending.
/// @return Updated market balances
function getLastMarketState(IDahlia.Market memory market, uint256 lendAssets) internal view returns (IDahlia.Market memory) {
    uint256 totalBorrowAssets = market.totalBorrowAssets;
    uint256 deltaTime = block.timestamp - market.updatedAt;
-
    if ((deltaTime != 0 || lendAssets != 0) && totalBorrowAssets != 0 && address(market.irm) != address(0)) {
-
        uint256 totalLendAssets = market.totalLendAssets + lendAssets;
-
        uint256 totalLendShares = market.totalLendShares;
-
        uint256 fullUtilizationRate = market.fullUtilizationRate;
-
        uint256 reserveFeeRate = market.reserveFeeRate;
-
        uint256 protocolFeeRate = market.protocolFeeRate;
-
        (uint256 interestEarnedAssets, uint256 newRatePerSec, uint256 newFullUtilizationRate) =
            IIrm(market.irm).calculateInterest(deltaTime, totalLendAssets, totalBorrowAssets, fullUtilizationRate);
-
        uint256 protocolFeeShares = calcFeeSharesFromInterest(totalLendAssets, totalLendShares, interestEarnedAssets, protocolFeeRate);
-
        uint256 reserveFeeShares = calcFeeSharesFromInterest(totalLendAssets, totalLendShares, interestEarnedAssets, reserveFeeRate);
-
        market.totalLendShares = totalLendShares + protocolFeeShares + reserveFeeShares;
        market.fullUtilizationRate = uint64(newFullUtilizationRate);
        market.ratePerSec = uint64(newRatePerSec);
-
        market.totalBorrowAssets += interestEarnedAssets;
        market.totalLendAssets += interestEarnedAssets;
    }
    return market;
}
```

The new implementation would look like this:

```solidity
function getLastMarketState(IDahlia.Market memory market, uint256 lendAssets) internal view returns (IDahlia.Market memory) {
    uint256 totalBorrowAssets = market.totalBorrowAssets;
    uint256 deltaTime = block.timestamp - market.updatedAt;
    // 1. accrue market interest
    if (deltaTime != 0 && totalBorrowAssets != 0 && address(market.irm) != address(0)) {
        uint256 totalLendAssets = market.totalLendAssets;
        (uint256 interestEarnedAssets, uint256 newRatePerSec, uint256 newFullUtilizationRate) =
            IIrm(market.irm).calculateInterest(deltaTime, totalLendAssets, totalBorrowAssets, market.fullUtilizationRate);
        market.fullUtilizationRate = uint64(newFullUtilizationRate);
        market.ratePerSec = uint64(newRatePerSec);
        if (interestEarnedAssets > 0) {
            uint256 totalLendShares = market.totalLendShares;
            uint256 protocolFeeShares = calcFeeSharesFromInterest(totalLendAssets, totalLendShares, interestEarnedAssets, market.protocolFeeRate);
            uint256 reserveFeeShares = calcFeeSharesFromInterest(totalLendAssets, totalLendShares, interestEarnedAssets, market.reserveFeeRate);
            market.totalLendShares = totalLendShares + protocolFeeShares + reserveFeeShares;
            market.totalBorrowAssets += interestEarnedAssets;
            market.totalLendAssets += interestEarnedAssets;
        }
    }
    if (lendAssets > 0) {
        market.totalLendAssets += lendAssets;
        market.totalLendShares += lendAssets.toSharesDown(market.totalLendAssets, market.totalLendShares);
    }
    market.updatedAt = uint48(block.timestamp);
    return market;
}
```

Notes:
1. market.updatedAt is updated at the end unconditionally to make calling this function multiple times cheaper, since the interest accrual would need to only happen once.
2. market.fullUtilizationRate and market.ratePerSec are updated irregardless of whether interestEarnedAssets is non-zero or not.
3. This new and old implementation have the assumption that the interest accrual only need to happen when totalBorrowAssets is non-zero although there could be some custom IIrm implementations that would return values for even if totalBorrowAssets is 0.
4. The above implementation is not the most gas-efficient one. Further optimisations can be applied.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the market state simulation routine that is used to predict lending rates after a deposit. The routine is supposed to first accrue interest on the existing market balances and only afterwards apply the effect of a new deposit. In the current implementation the order is reversed: when a non‑zero deposit amount is supplied (as happens in the previewLendRateAfterDeposit call) the function adds the deposit amount to the market’s total lend assets before interest is accrued, and it also fails to increase the market’s totalLendAssets with the deposit at all. Consequently the interest calculation is performed on an inflated lend balance and the resulting rate is lower than it should be. This incorrect rate propagates to WrappedVault.previewRateAfterDeposit and is later compared against the incentives rates requested by an offer. Because the previewed rate is artificially low, the protocol may accept offers whose incentives exceed the true available rate, violating the condition checked in VaultMarketHub.allocateOffer. The bug is triggered whenever previewLendRateAfterDeposit is called with a positive lendAssets argument, i.e., during a deposit preview. It affects any user or protocol component that relies on accurate rate previews, including lenders who expect a certain return and the vault that enforces incentive constraints. The issue was discovered during a manual audit that examined the flow of data through the preview functions and noticed that the market state was not updated correctly for the deposit case. It is subtle because the function is used in many places with a zero deposit argument, where the calculations appear correct, masking the problem in the preview path. From a user perspective the symptom is that a deposit preview shows a more favorable rate than what will actually be applied, leading to expectations of higher returns that are not met, and potentially allowing offers that drain incentives from the vault. The root cause is a logical ordering error and an omission of the deposit amount from the market’s total lend assets during the simulation. The proper fix is to separate interest accrual from the deposit simulation, first compute interest based on the pre‑deposit balances, then add the deposit amount to totalLendAssets and totalLendShares, and finally update the market timestamp. This restores the correct accounting order and ensures that rate previews reflect the true post‑deposit state.
