---
id: 11382
severity: "High"
---

# Total market debt > 0 when credit deposits > netusdissuance which breaks key protocol logic

## Description

```solidity
function depositCreditForMarket(
        uint128 marketId,
        address collateralAddr,
        uint256 amount
    )
        external
        onlyRegisteredEngine(marketId)
    {
        if (amount == 0) revert Errors.ZeroInput("amount");

        // loads the collateral's data storage pointer, must be enabled
        Collateral.Data storage collateral = Collateral.load(collateralAddr);
        collateral.verifyIsEnabled();

        // loads the market's data storage pointer, must have delegated credit so
        // engine is not depositing credit to an empty distribution (with 0 total shares)
        // although this should never happen if the system functions properly.
        Market.Data storage market = Market.loadLive(marketId);
        if (market.getTotalDelegatedCreditUsd().isZero()) {
            revert Errors.NoDelegatedCredit(marketId);
        }

        // uint256 -> UD60x18 scaling decimals to zaros internal precision
        UD60x18 amountX18 = collateral.convertTokenAmountToUd60x18(amount);

        // caches the usdToken address
        address usdToken = MarketMakingEngineConfiguration.load().usdTokenOfEngine[msg.sender];

        // caches the usdc
        address usdc = MarketMakingEngineConfiguration.load().usdc;

        // note: storage updates must occur using zaros internal precision
        if (collateralAddr == usdToken) {
            // if the deposited collateral is USD Token, it reduces the market's realized debt
            market.updateNetUsdTokenIssuance(unary(amountX18.intoSD59x18()));
        } else {
            if (collateralAddr == usdc) {
                market.settleCreditDeposit(address(0), amountX18);
            } else {
                // deposits the received collateral to the market to be distributed to vaults
                // to be settled in the future
                market.depositCredit(collateralAddr, amountX18);
            }
        }

        // transfers the margin collateral asset from the registered engine to the market making engine
        // NOTE: The engine must approve the market making engine to transfer the margin collateral asset, see
        // PerpsEngineConfigurationBranch::setMarketMakingEngineAllowance
        // note: transfers must occur using token native precision
        IERC20(collateralAddr).safeTransferFrom(msg.sender, address(this), amount);

        // emit an event
        emit LogDepositCreditForMarket(msg.sender, marketId, collateralAddr, amount);
    }
```
Credit Deposits are incremented when the perp engine deposits a non-usdc or usd token of engine to the market making engine. The total market debt is calculated using this function:
```solidity
function getTotalDebt(Data storage self) internal view returns (SD59x18 totalDebtUsdX18) {
        totalDebtUsdX18 = getUnrealizedDebtUsd(self).add(getRealizedDebtUsd(self));
    }
```
Market::getRealizedDebt is calculated with:
```solidity
/// @return realizedDebtUsdX18 The market's net realized debt in USD as SD59x18.
    function getRealizedDebtUsd(Data storage self) internal view returns (SD59x18 realizedDebtUsdX18) {
        // prepare the credit deposits usd value variable;
        UD60x18 creditDepositsValueUsdX18;

        // if the credit deposits usd value cache is up to date, return the stored value
        if (block.timestamp <= self.lastCreditDepositsValueRehydration) {
            creditDepositsValueUsdX18 = ud60x18(self.creditDepositsValueCacheUsd);
        } else {
            // otherwise, we'll need to loop over credit deposits to calculate it
            creditDepositsValueUsdX18 = getCreditDepositsValueUsd(self);
        }

        // finally after determining the market's latest credit deposits usd value, sum it with the stored net usd
        // token issuance to return the net realized debt usd value
        realizedDebtUsdX18 = creditDepositsValueUsdX18.intoSD59x18().add(sd59x18(self.netUsdTokenIssuance));
    }
```
This realized debt calculates how much non-usdc tokens that are in the marketmakingengine contract which is Market::creditDepositsValueUsdX18 and 'adds' it to the Market::netusdtokenissuance. I say add in quotation because Market::netusdtokenissuance will always be negative. Market::netusdtokenissuance is updated whenever perp engine sends usd token of engine back to the marketmakingengine contract using CreditDelegationBranch::depositCreditForMarket. if usd token of engine is sent back to the contract, then that means that there is less usdz that zaros has to redeem 1:1 for usdc. If there is less usd token engine to account for, then zaros has less debt. Using the logic from the protocol, total debt is supposed to be positive if netusdissuance > credit deposits but instead the opposite is the case where market debt is positive when credit deposits > net usd token issuance.

Incorrect Debt and Credit Allocation: Instead of market debt being positive when netUsdTokenIssuance > creditDeposits, the current implementation inverts this logic, making credit deposits appear as market debt. As a result, vaults inaccurately register as being in debt when they should be in credit, and vice versa.

Incorrect Reward Distribution: Since vaults earn rewards based on their credit participation, an incorrect debt calculation could lead to underpayment for vaults that should be in credit and overpayment to vaults that should be in debt. This weakens the integrity of the reward distribution model, making the system unreliable for liquidity providers.

## Proof of Concept

```solidity
function test_debtvaluenonnegativewhencreditdepositsgtnetusdissuance(uint128 vaultId,
        uint128 marketId
    )
        external
    {
        vm.stopPrank();
        // configure vaults and markets
        VaultConfig memory fuzzVaultConfig = getFuzzVaultConfig(vaultId);
        vm.assume(fuzzVaultConfig.asset != address(wBtc)); // to avoid overflow issues
        vm.assume(fuzzVaultConfig.asset != address(usdc)); // to log market debt
        PerpMarketCreditConfig memory fuzzMarketConfig = getFuzzPerpMarketCreditConfig(marketId);

        uint256[] memory marketIds = new uint256[](1);
        marketIds[0] = fuzzMarketConfig.marketId;

        uint256[] memory vaultIds = new uint256[](1);
        vaultIds[0] = fuzzVaultConfig.vaultId;

        vm.prank(users.owner.account);
        marketMakingEngine.connectVaultsAndMarkets(marketIds, vaultIds);

        address engine = marketMakingEngine.workaround_getMarketEngine(fuzzMarketConfig.marketId);
        
        address usdtoken = marketMakingEngine.workaround_getUsdTokenOfEngine(engine);

        // perp engine deposits credit into market to incur debt
        deal(fuzzVaultConfig.asset, address(fuzzMarketConfig.engine), 100e18);
        deal(usdtoken, address(fuzzMarketConfig.engine), 100e18);
        vm.startPrank(address(fuzzMarketConfig.engine));
        marketMakingEngine.depositCreditForMarket(fuzzMarketConfig.marketId, fuzzVaultConfig.asset, 10e18);

        // perp engine now deposits usd token into market but less than credit deposits
        marketMakingEngine.depositCreditForMarket(fuzzMarketConfig.marketId, usdtoken, 5e18);

        vm.stopPrank();

        marketMakingEngine.updateVaultCreditCapacity(fuzzVaultConfig.vaultId);

        /* get total credit deposits of market
        add the selector of workaround_getCreditDepositsValueUsd to the marketharness array in TreeProxyUtils.sol and increment the bytes array size by 1 to run this test
        */
        uint256 marketcreditdeposit = marketMakingEngine.workaround_getCreditDepositsValueUsd(fuzzMarketConfig.marketId);
        console.log(marketcreditdeposit);

        // get net usd token issuance
        int128 netusdissuance = marketMakingEngine.workaround_getMarketUsdTokenIssuance(fuzzMarketConfig.marketId);
        console.log(netusdissuance);

        // get debt value
        SD59x18 debtvalue = marketMakingEngine.workaround_getTotalMarketDebt(fuzzMarketConfig.marketId);  
        console.log(debtvalue.unwrap());

        // when creditdeposits > netusdissuance, debt is a positive number which breaks protocol logic
        assert(debtvalue.unwrap() > 0);
    }
```

## Recommendation

```solidity
// Corrected Debt Calculation:
realizedDebtUsdX18 = sd59x18(self.netUsdTokenIssuance).sub(creditDepositsValueUsdX18.intoSD59x18());
```
Since netUsdTokenIssuance represents debt issuance, it should be positive when debt is high. creditDepositsValueUsdX18 represents assets held, which reduces the market’s net debt.

Modify the CreditDelegationBranch::depositCreditForMarket function so that USDC deposits correctly reduce debt and credit deposits increase the credit balance and do not incorrectly inflate the market’s debt.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inverted accounting rule in the market‑making engine that determines the total market debt. The protocol is supposed to treat the net USD token issuance as a positive debt amount and to reduce that debt by the value of credit deposits held by the market. Instead, the realized debt calculation adds the USD value of credit deposits to the net USD token issuance, which is stored as a negative number. Consequently, when the amount of credit deposited exceeds the net USD token issuance, the resulting total debt becomes a positive value, contrary to the intended business logic. This inversion occurs in the function that aggregates unrealized and realized debt, where the realized component is computed as creditDepositsValueUsdX18 + netUsdTokenIssuance. Because netUsdTokenIssuance is negative, adding the credit deposits effectively treats them as additional debt rather than a reduction. The bug is triggered whenever a perp engine deposits more non‑USDC collateral (or USD token of engine) than the amount of USD token that has been returned to the market, i.e., when creditDeposits > netUsdTokenIssuance. Under these conditions the market reports a positive debt, vaults are incorrectly marked as being in debt, and reward distribution based on credit participation becomes distorted – vaults that should earn rewards receive less, while those that should be penalised receive more. From a user perspective this manifests as vault balances appearing negative or zero after a deposit, missing or unexpectedly low reward payouts, and overall confusion about the state of their positions. The issue was discovered during a high‑severity audit by CodeHawks, where a fuzz test deliberately created a scenario with credit deposits greater than net USD issuance and asserted that the total debt should not be positive; the assertion failed, exposing the inverted logic. The problem is subtle because the debt value remains a numeric figure that can be positive or negative, and without dissecting the individual components it is easy to assume the calculation is correct. The root cause is a conceptual mistake in the debt formula: credit deposits should subtract from net debt, not add to it. The recommended fix is to compute realized debt as netUsdTokenIssuance minus creditDepositsValueUsdX18, thereby restoring the intended accounting relationship. Adjusting the depositCreditForMarket handling of USDC deposits to correctly reduce debt and ensuring credit deposits only increase the credit balance will also prevent the market from inflating its debt erroneously. This correction re‑aligns vault accounting with protocol expectations, restores accurate reward distribution, and eliminates the risk of vaults being mistakenly penalised or over‑rewarded due to faulty debt calculations.
