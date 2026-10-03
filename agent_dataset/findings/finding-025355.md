---
id: 25355
severity: "Low/Info"
---

# Inactive or Impaired pool creates arbitrage oportunities

## Description

When assetsUnderManagement() decreases, a window of opportunity is created for people to stake in the maple pool very cheaply and then sell for profit when it becomes active again or the protocol admin calls withdrawFromStrategy().

For inactive: This [test](<https://github.com/maple-labs/maple-core-v2-private/blob/main/tests/integration/strategies/AaveStrategy.t.sol#L586>) shows that users may stake in the maple pool and get a lot of shares, protocol admin withdraws from strategy, instantly increasing the total assets of the pool. pool.totalAssets() goes from poolLiquidity - amountToFund to poolLiquidity amountToFund + amountToWithdraw instantly, so a user stakes like 1000, gets 1000 shares, protocol admin withdraws from strategy and then user redeems for 1500 assets.

For impairment: This [test](<https://github.com/maple-labs/maple-core-v2-private/blob/main/tests/integration/strategies/AaveStrategy.t.sol#L540>) shows that users can do the same thing, but the profit is much smaller, as only the fee in pool.totalAssets() differs from before and after withdrawFromStrategy().

## Proof of Concept

No PoC provided.

## Recommendation

This can be managed operationally by disabling deposits in the pool while the strategy is impaired/inactive.
