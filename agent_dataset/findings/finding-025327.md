---
id: 25327
severity: "Medium"
---

# Liquidation can be finished without calling triggerDefault() (and repossessing the loan) if pool delegate or governor call finishCollateralLiquidation(...) after impairment.

## Description

The usual flow is to impair a loan and then call triggerDefault() followed by finishCollateralLiquidation(); however, it's possible to call finishCollateralLiquidation() without calling triggerDefault(), leading to the collateral in the loan not being liquidated and the cover of the delegate being used. Exploit scenario

- delegate or governor impair a loan
- delegate or governor call finishCollateralLiquidation(...) without calling triggerDefault(...) first
- The liquidationInfo is deleted, the collateral in the loan is not repossessed and the cover of the delegate is used to cover the remaining losses (if available)
- principalOut in the loan manager will decrease by the principal amount
- The paymentId of the loan will not be deleted, so if the borrower decides to make a payment / close the loan at any time, and this call updates the principalOut the following 2 scenarios are possible:
- If the loan is the only loan in the loan manager, it will revert
- If there are more loans, it will decrease the principalOut and it can make the other loans' payments fail

## Proof of Concept

No PoC provided.

## Recommendation

Check if the address of the liquidator is 0 at the beginning of the finishCollateralLiquidation() function.
