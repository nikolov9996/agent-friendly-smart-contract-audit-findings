---
id: 25016
severity: "Crit/High"
---

# Missing Update to omnichain.totalAvailableLiquidationAmount in withdrawUser

## Description



## Proof of Concept

1. State Before Withdrawal:

- omnichain.totalAvailableLiquidationAmount = 1,000,000 USDa.
- User withdraws 200,000 USDa.

2. Expected Behavior:

- omnichain.totalAvailableLiquidationAmount is reduced to 800,000 USDa.

3. Actual Behavior:

- omnichain.totalAvailableLiquidationAmount remains 1,000,000 USDa.

4. During Liquidation:

- Assume liquidation generates 500,000 USDa in gains.
- Share calculation uses the inflated 1,000,000 USDa instead of the actual 800,000 USDa.
- 100,000 USDa of the gains remains locked due to the overestimated pool size.

## Impact

1. A portion of liquidation gains remains locked in the CDS pool, reducing the funds distributed to eligible users.
2. Remaining CDS participants receive a smaller share of the liquidation gains than they are entitled to.

## Recommendation

```javascript
params.omniChainData.totalAvailableLiquidationAmount -= params.cdsDepositDetails.withdrawedAmount;
```

I should note there seems to be no update on omnichain, this should be looked at
