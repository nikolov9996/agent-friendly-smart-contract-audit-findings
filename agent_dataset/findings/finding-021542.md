---
id: 21542
severity: "Medium"
---

# Users can not to buy/sell minimum credit allowed due to exactAmountIn condition

## Description

The minimum credit user can buy or sell can be gotten from `state.riskConfig.minimumCreditBorrowAToken` which was set as `5e6`. However, in `buyCreditMarket` and `sellCreditMarket` user can not buy or sell minimun credit allowed or small amount above it due to the `exactAmountIn` condition he chose.

**In `buyCreditMarket`:** when user set `params.exactAmountIn = true`, The `params.amount` value will be cash he want to use to buy credit. Since the `params.amount` value is cash it can be set less than `state.riskConfig.minimumCreditBorrowAToken` (5e6) as long as when the value get converted to credit it will reach the `state.riskConfig.minimumCreditBorrowAToken` value. But, unfortunately, in `validateBuyCreditMarket()` whenever `params.amount` is less than `state.riskConfig.minimumCreditBorrowAToken` the transaction will revert due to below code present in the function.

```solidity
if (params.amount < state.riskConfig.minimumCreditBorrowAToken) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

For example, the cash user can use to buy minimum credit allowed (`5e6`) can be calculated as in the code below, And the value should be less than the minimum credit allowed (`5e6`).

```solidity
uint256 minimumCash = Math.mulDivUp(5e6, PERCENT, PERCENT + ratePerTenor);
```

**In `sellCreditMarket`:** when user set `params.exactAmountIn = false`, The `params.amount` will be the exact cash he want to receive. But he will also not be able to set the `params.amount` value to be less than `state.riskConfig.minimumCreditBorrowAToken` value due to the below code present in `validateSellCreditMarket()`.

```solidity
if (params.amount < state.riskConfig.minimumCreditBorrowAToken) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

## Proof of Concept

**For `BuyCreditMarket`:** Copy and paste below code in `/test/local/actions/BuyCreditMarket.t.sol`:

```solidity
function testFail_UserCanNotBuyMinimumCredit() public {
    // alice deposit weth
    _deposit(alice, weth, 100e18);

    // bob deposit usdc
    _deposit(bob, usdc, 200e6);

    // alice create a borrow offer
    _sellCreditLimit(alice, 0.03e18, 365 days);

    // calculate cash from minimum  credit borrowAToken allowed = 5e6
    uint256 minimumCash = Math.mulDivUp(5e6, PERCENT, PERCENT + 0.03e18);

    // Expect revert with an error CREDIT_LOWER_THAN_MINIMUM_CREDIT
    uint256 debtPositionId = _buyCreditMarket(bob, alice, minimumCash, 365 days, true);
}
```

Then run the test with below command, the test should pass because it will revert with an error `Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT`.

    forge test --mt testFail_UserCanNotBuyMinimumCredit

**For `SellCreditMarket`:** Copy and paste below code in `/test/local/actions/SellCreditMarket.t.sol`:

```solidity
function testFail_UserCanNotSellMinimumCredit() public {
    // alice deposit usdc
    _deposit(alice, usdc, 200e6);

    // bob deposit weth
    _deposit(bob, weth, 100e18);

    // alice create a loan offer
    _buyCreditLimit(alice, block.timestamp + 365 days, YieldCurveHelper.pointCurve(365 days, 0.03e18));

    // calculate cash from minimum  credit borrowAToken allowed = 5e6
    uint256 minimumCreditInCash = Math.mulDivUp(5e6, PERCENT, PERCENT + 0.03e18);

    // Expect revert with an error CREDIT_LOWER_THAN_MINIMUM_CREDIT
    uint256 debtPositionId = _sellCreditMarket(bob, alice, RESERVED_ID, minimumCreditInCash, 365 days, false);
}
```

Then run the test with below command, the test should pass because it will revert with an error `Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT`.

    forge test --mt testFail_UserCanNotSellMinimumCredit

## Recommendation

In `validateBuyCreditMarket()` and `validateSellCreditMarket()` for `BuyCreditMarket` and `SellCreditMarket` libraries respectively, there is a need of considering the condition of `params.exactAmountIn` value. The check should be implemented as shown below.

**For `BuyCreditMarket` library:** inside `validateBuyCreditMarket()` replace below code:

```solidity
if (params.amount < state.riskConfig.minimumCreditBorrowAToken) { // @audit 5e6 USDC
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

With the below code:

```solidity
uint256 ratePerTenor = borrowOffer.getRatePerTenor(VariablePoolBorrowRateParams({variablePoolBorrowRate: state.oracle.variablePoolBorrowRate, variablePoolBorrowRateUpdatedAt: state.oracle.variablePoolBorrowRateUpdatedAt, variablePoolBorrowRateStaleRateInterval: state.oracle.variablePoolBorrowRateStaleRateInterval}), tenor);

if (params.exactAmountIn && params.amount < Math.mulDivUp(state.riskConfig.minimumCreditBorrowAToken, PERCENT, PERCENT + ratePerTenor)) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
} else if (!params.exactAmountIn && params.amount < state.riskConfig.minimumCreditBorrowAToken) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

**For `SellCreditMarket` library:** inside `validateSellCreditMarket()` replace below code:

```solidity
if (params.amount < state.riskConfig.minimumCreditBorrowAToken) { // @audit 5e6 USDC
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

With the below code:

```solidity
uint256 ratePerTenor = loanOffer.getRatePerTenor(VariablePoolBorrowRateParams({variablePoolBorrowRate: state.oracle.variablePoolBorrowRate, variablePoolBorrowRateUpdatedAt: state.oracle.variablePoolBorrowRateUpdatedAt, variablePoolBorrowRateStaleRateInterval: state.oracle.variablePoolBorrowRateStaleRateInterval}), tenor);

if (params.exactAmountIn && params.amount < state.riskConfig.minimumCreditBorrowAToken) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
} else if (!params.exactAmountIn && params.amount < Math.mulDivUp(state.riskConfig.minimumCreditBorrowAToken, PERCENT, PERCENT + ratePerTenor)) {
    revert Errors.CREDIT_LOWER_THAN_MINIMUM_CREDIT(params.amount, state.riskConfig.minimumCreditBorrowAToken);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract enforces a minimum credit amount of 5e6 units that can be borrowed or sold, but the validation logic in both the buy and sell market functions checks the raw cash amount supplied by the user (params.amount) against this credit minimum without taking into account the exactAmountIn flag and the conversion rate between cash and credit. When a user sets exactAmountIn to true for a buy operation, params.amount represents the cash they are willing to spend; the amount of cash required to obtain the minimum credit can be lower than the credit minimum after applying the rate per tenor, yet the code unconditionally reverts if params.amount is less than 5e6. The same mistake occurs for sell operations when exactAmountIn is false, causing the transaction to revert even though the cash amount would correspond to the minimum credit after conversion. This mismatch between the unit of measurement used in the check and the unit expected by the user prevents legitimate trades that meet the business rule of minimum credit, leading to a user‑facing symptom where the transaction fails with the error CREDIT_LOWER_THAN_MINIMUM_CREDIT, the user receives no credit or cash, and balances remain unchanged. The root cause is an improper input validation that ignores the conversion formula and the exactAmountIn flag, a classic example of a business‑logic validation bug where the wrong domain variable is compared. The issue manifests whenever a user attempts to buy or sell the smallest allowed credit using the exact amount mode, affecting any participant in the market – borrowers, lenders, or liquidity providers – and can reduce protocol usability and liquidity. It was discovered during a security audit when test cases attempted to execute a trade with the minimum credit amount and observed an unexpected revert. The bug can be hard to notice because the check appears reasonable at first glance, but it violates the accounting assumption that cash and credit are interchangeable after applying the rate. The recommended fix is to adjust the validation to compare the cash amount against the minimum credit only after applying the appropriate conversion when exactAmountIn is true, and to keep the original check for the opposite mode, thereby aligning the validation with the intended business rule and restoring the ability to trade the minimum credit amount.
