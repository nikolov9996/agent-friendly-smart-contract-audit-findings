---
id: 25187
severity: "Medium"
---

# BorrowingVault, if the debt/assets ratio falls too much, liquidators could choose to repay debt equal to the assets at a discount

## Description

Currently the borrowing vault enables liquidating a user's position 50% if the debt/assets ratio is above liqRatio, but below liqRatio / FULL_LIQUIDATION_THRESHOLD.

If the ratio debt/assets increases too much, a liquidation might not be profitable for liquidators, because users might not have enough assets. In this scenario, it could be possible to completely close the user position by paying back the debt corresponding to the assets of the user. This will still leave some amount of bad debt, but hopefully much less.

In the current implementation, if a specific collateral asset drops too much, it could happen that many liquidations would not be profitable and a lot of bad debt would appear. This bad debt could be limited with this recommendation. In the end, it could prevent a liquidation in a provider.

Example: 75 debt, 100 assets asset/debt value falls to 0.74 paying 75 debt, would give the liquidator 100 assets, which is equivalent to 74 debt at 0.74 price, not profitable. This would leave 75 bad debt in the protocol

## Proof of Concept

No PoC provided.

## Recommendation

Let the liquidators "close" the position of the user by getting 100 assets for the corresponding debt at a discount. Same Example: Letting liquidators choose to repay the debt corresponding to the total amount of assets, if these are worth less than the debt, would help keep the protocol healthier.

In this case, let's say a liquidator wants to repay the 100 assets, it would cost assets * price * LIQUIDATION_PENALTY = 100 * 0.74 * 0.9 = 66.6 debt. This would leave 8.4 bad debt in the protocol.

Note that the current liquidation logic would require skipping the maxRedeem(...) of the user, if the liquidation is not profitable, userAssets < userDebt * price * 10 ** _asset.decimals().
