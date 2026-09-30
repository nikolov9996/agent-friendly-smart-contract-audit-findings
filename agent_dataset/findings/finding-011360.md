---
id: 11360
severity: "High"
---

# The Deleverage Will apply twice on market USDtoken minting

## Description

When the _fillOrder is called we check that if the old position of user has some PNL, than we check that adjust profit and tries to find if any deleverage could be applied otherwise the PNL value will be provided withdrawUsdTokenFromMarket, the issue arises in case when deleverage factor could be applied in this case the getAdjustedProfitForMarketId returns the value on which we have applied the deleverage factor and pass that value to withdrawUsdTokenFromMarket which also applies Deleverage factor, so in this case the market will receive less usdToken than expected.

let have a look on how the issue occurs:
first we will call fillOrder function which check that pnlUsdX18>0, than we calls getAdjustedProfitForMarketId.
```solidity
/src/perpetuals/branches/SettlementBranch.sol:496
if (ctx.pnlUsdX18.gt(SD59x18_ZERO)) {
    IMarketMakingEngine marketMakingEngine = IMarketMakingEngine(perpsEngineConfiguration.marketMakingEngine);

    ctx.marginToAddX18 =
        marketMakingEngine.getAdjustedProfitForMarketId(marketId, ctx.pnlUsdX18.intoUD60x18().intoUint256());

    tradingAccount.deposit(perpsEngineConfiguration.usdToken, ctx.marginToAddX18);

    // mint settlement tokens credited to trader; tokens are minted to
    // address(this) since they have been credited to the trader's margin
    marketMakingEngine.withdrawUsdTokenFromMarket(marketId, ctx.marginToAddX18.intoUint256());
}
```
The getAdjustedProfitForMarketId function will checks that if the deleverage factor could be applied in our case we assumes that it could be applied:
```solidity
/src/market-making/branches/CreditDelegationBranch.sol:129
function getAdjustedProfitForMarketId(
    uint128 marketId,
    uint256 profitUsd
)
    public
    view
    returns (UD60x18 adjustedProfitUsdX18)
{
    // load the market's data storage pointer & cache total debt
    Market.Data storage market = Market.loadLive(marketId);
    SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();

    // caches the market's delegated credit & credit capacity
    UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();
    SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

    // if the credit capacity is less than or equal to zero then
    // the total debt has already taken all the delegated credit
    if (creditCapacityUsdX18.lte(SD59x18_ZERO)) {
        revert Errors.InsufficientCreditCapacity(marketId, creditCapacityUsdX18.intoInt256());
    }

    // uint256 -> UD60x18; output default case when market not in Auto Deleverage state
    adjustedProfitUsdX18 = ud60x18(profitUsd);

    // we don't need to add profitUsd as it's assumed to be part of the total debt
    // NOTE: If we don't return the adjusted profit in this if branch, we assume marketTotalDebtUsdX18 is positive
    if (market.isAutoDeleverageTriggered(delegatedCreditUsdX18, marketTotalDebtUsdX18)) {
        // if the market's auto deleverage system is triggered, it assumes marketTotalDebtUsdX18 > 0
        adjustedProfitUsdX18 =
            market.getAutoDeleverageFactor(delegatedCreditUsdX18, marketTotalDebtUsdX18).mul(adjustedProfitUsdX18);
    }
}
```
At Line 158 we can see that it will return the profit value on which the deleverage factor is already applied than we pass this value to withdrawUsdTokenFromMarket function which again applies this factor:
```solidity
/src/market-making/branches/CreditDelegationBranch.sol:249
function withdrawUsdTokenFromMarket(uint128 marketId, uint256 amount) external onlyRegisteredEngine(marketId) {
    // loads the market's data and connected vaults
    Market.Data storage market = Market.loadLive(marketId);
    uint256[] memory connectedVaults = market.getConnectedVaultsIds();

    // once the unrealized debt is distributed update credit delegated
    // by these vaults to the market
    Vault.recalculateVaultsCreditCapacity(connectedVaults);

    // cache the market's total debt and delegated credit
    SD59x18 marketTotalDebtUsdX18 = market.getTotalDebt();
    UD60x18 delegatedCreditUsdX18 = market.getTotalDelegatedCreditUsd();

    // uint256 -> UD60x18
    // NOTE: we don't need to scale decimals here as it's known that USD Token has 18 decimals
    UD60x18 amountX18 = ud60x18(amount);

    // prepare the amount of usdToken that will be minted to the perps engine;
    // initialize to default non-ADL state
    uint256 amountToMint = amount;

    if (market.isAutoDeleverageTriggered(delegatedCreditUsdX18, marketTotalDebtUsdX18)) {
        // if the market is in the ADL state, it reduces the requested USD
        // Token amount by multiplying it by the ADL factor, which must be < 1
        UD60x18 adjustedUsdTokenToMintX18 =
            market.getAutoDeleverageFactor(delegatedCreditUsdX18, marketTotalDebtUsdX18).mul(amountX18);

        amountToMint = adjustedUsdTokenToMintX18.intoUint256();
        market.updateNetUsdTokenIssuance(adjustedUsdTokenToMintX18.intoSD59x18());

    // mint USD Token to the perps engine
    UsdToken usdToken = UsdToken(marketMakingEngineConfiguration.usdTokenOfEngine[msg.sender]);
    usdToken.mint(msg.sender, amountToMint);

    // emit an event
    emit LogWithdrawUsdTokenFromMarket(msg.sender, marketId, amount, amountToMint);
}
```
Here we can see Line 288 if isAutoDeleverageTriggered is true than we again apply deleverage factor and mint that value to market.

Due to applying twice deleverage factor the prep engine will receive less usdToken. So lose of funds for prep engine.

## Proof of Concept

The following POC will proof it:
```solidity
function test_WhenTheAutoDeleverageFactorIsTriggered(
    uint256 marketId
)
    external
    whenTheMarketIsLive
    whenTheCreditCapacityIsGreaterThanZero
{
    uint256 profitUsd = 10e18;

    PerpMarketCreditConfig memory fuzzMarketConfig = getFuzzPerpMarketCreditConfig(marketId);

    marketMakingEngine.workaround_setMarketUsdTokenIssuance(fuzzMarketConfig.marketId, 5e9 + 10);

    UD60x18 delegatedCreditUsdX18 =
        marketMakingEngine.workaround_getTotalDelegatedCreditUsd(fuzzMarketConfig.marketId);
    SD59x18 totalDebtUsdX18 = marketMakingEngine.workaround_getTotalMarketDebt(fuzzMarketConfig.marketId);

    UD60x18 autoDeleverageFactorX18 = marketMakingEngine.workaround_getAutoDeleverageFactor(
        fuzzMarketConfig.marketId, delegatedCreditUsdX18, totalDebtUsdX18
    );

    UD60x18 adjustedProfitUsdX18 =
        marketMakingEngine.getAdjustedProfitForMarketId(fuzzMarketConfig.marketId, profitUsd);
    console.log("adjustedProfitUsdX18", adjustedProfitUsdX18.intoUint256());
    console.log("autoDeleverageFactorX18", autoDeleverageFactorX18.intoUint256());

    uint256 balBefore = IERC20(usdToken).balanceOf(address(perpsEngine));
    // it should return the adjusted profit
    // applying the Deleveraging factor we exepect to mint this much adjustedProfitUsdX18 to market 
    assertEq(ud60x18(profitUsd).mul(autoDeleverageFactorX18).intoUint256(), adjustedProfitUsdX18.intoUint256());
    changePrank({ msgSender: address(perpsEngine) });
    marketMakingEngine.withdrawUsdTokenFromMarket(fuzzMarketConfig.marketId, adjustedProfitUsdX18.intoUint256());
    uint256 balAfter = IERC20(usdToken).balanceOf(address(perpsEngine));

    assertNotEq(adjustedProfitUsdX18.intoUint256(), balAfter - balBefore);
    // but the code apply deleverage twice
    adjustedProfitUsdX18 = adjustedProfitUsdX18.mul(autoDeleverageFactorX18);
    assertEq(adjustedProfitUsdX18.intoUint256(), balAfter - balBefore);
}
```
Add the above test in CreditDelegationBranchGetAdjustedProfitForMarketIdIntegration_Test test contract and run with command: forge test --mt test_WhenTheAutoDeleverageFactorIsTriggered -vvv

## Recommendation

Pass the exact PNL value to withdrawUsdTokenFromMarket or remove the deleverage factor calculation for withdrawUsdTokenFromMarket function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract suffers from a double‑application of the auto‑deleverage factor when a trader closes a profitable position. When the settlement branch processes a fillOrder with a positive PNL, it first calls getAdjustedProfitForMarketId, which checks the market’s credit capacity and, if the auto‑deleverage state is active, multiplies the raw profit by the deleverage factor. The function then returns this already‑adjusted profit and the settlement code deposits it as margin and immediately forwards the same amount to withdrawUsdTokenFromMarket. The withdraw function repeats the same auto‑deleverage check and, if the market is still in the deleverage state, multiplies the received amount by the same factor again before minting USD tokens. As a result the perps engine receives only profit × factor × factor instead of profit × factor, meaning the engine’s USD token balance is lower than expected. This can be triggered whenever a market has a positive PNL and its credit capacity is exhausted, i.e., the auto‑deleverage condition is true. The bug primarily affects the perps engine and any trader relying on correct profit settlement, leading to missing funds, reduced margin, and potential liquidation. It was discovered during a manual audit and confirmed with a targeted unit test that showed the minted amount differed from the adjusted profit. The issue is subtle because each individual function behaves correctly in isolation; only their composition causes the factor to be applied twice, which is not obvious from a superficial code review. The vulnerability belongs to the class of arithmetic scaling bugs where an already‑scaled value is scaled again, violating the accounting assumption that profit adjustments are applied exactly once. From a user’s perspective the UI would show a successful trade but the reported balance increase would be smaller than expected, often appearing as “my profit disappeared” or “I received less USD token than I should have”. The correct fix is to ensure that withdrawUsdTokenFromMarket receives the raw PNL (without the deleverage factor) or to remove the second factor application inside withdrawUsdTokenFromMarket, guaranteeing that the profit is adjusted exactly once before minting.
