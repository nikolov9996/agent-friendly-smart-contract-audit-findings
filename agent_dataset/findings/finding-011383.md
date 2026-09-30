---
id: 11383
severity: "High"
---

# Incorrect calculation in CreditDelegationBranch::withdrawUsdTokenFromMarket allows attacker mint any amount of usdz

## Description

Market::getCreditCapacityUsd function located in CreditDelegationBranch::withdrawUsdTokenFromMarket, which incorrectly calculates the credit capacity of a market by adding the total debt to the delegated credit instead of subtracting it. This flaw leads to an overestimation of the market's credit capacity, potentially allowing the system to operate in an unsafe state where it cannot cover its liabilities. This issue is particularly severe because it affects the core logic of credit delegation and debt management in the protocol and allows an attacker to mint an amount of usdz that the protocol cannot back 1:1 with usdc which breaks a key protocol invariant.

CreditDelegationBranch::withdrawUsdTokenFromMarket contains the following code:
```solidity
/// @notice Mints the requested amount of USD Token to the caller and updates the market's
    /// debt state.
    /// @dev Called by a registered engine to mint USD Token to profitable traders.
    /// @dev USD Token association with an engine's user happens at the engine contract level.
    /// @dev We assume amount is part of the market's reported unrealized debt.
    /// @dev Invariants:
    /// The Market of marketId MUST exist.
    /// The Market of marketId MUST be live.
    /// @param marketId The engine's market id requesting USD Token.
    /// @param amount The amount of USD Token to mint.
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

        // calculate the market's credit capacity
        SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);

        // enforces that the market has enough credit capacity, if it's a listed market it must always have some
        // delegated credit, see Vault.Data.lockedCreditRatio.
        // NOTE: additionally, the ADL system if functioning properly must ensure that the market always has credit
        // capacity to cover USD Token mint requests. Deleverage happens when the perps engine calls
        // CreditDelegationBranch::getAdjustedProfitForMarketId.
        // NOTE: however, it still is possible to fall into a scenario where the credit capacity is <= 0, as the
        // delegated credit may be provided in form of volatile collateral assets, which could go down in value as
        // debt reaches its ceiling. In that case, the market will run out of mintable USD Token and the mm engine
        // must settle all outstanding debt for USDC, in order to keep previously paid USD Token fully backed.
        if (creditCapacityUsdX18.lte(SD59x18_ZERO)) {
            revert Errors.InsufficientCreditCapacity(marketId, creditCapacityUsdX18.intoInt256());
        }

        // uint256 -> UD60x18
        // NOTE: we don't need to scale decimals here as it's known that USD Token has 18 decimals
        UD60x18 amountX18 = ud60x18(amount);

        // prepare the amount of usdToken that will be minted to the perps engine;
        // initialize to default non-ADL state
        uint256 amountToMint = amount;

        // now we realize the added usd debt of the market
        // note: USD Token is assumed to be 1:1 with the system's usd accounting
        if (market.isAutoDeleverageTriggered(delegatedCreditUsdX18, marketTotalDebtUsdX18)) {
            // if the market is in the ADL state, it reduces the requested USD
            // Token amount by multiplying it by the ADL factor, which must be < 1
            UD60x18 adjustedUsdTokenToMintX18 =
                market.getAutoDeleverageFactor(delegatedCreditUsdX18, marketTotalDebtUsdX18).mul(amountX18);

            amountToMint = adjustedUsdTokenToMintX18.intoUint256();
            market.updateNetUsdTokenIssuance(adjustedUsdTokenToMintX18.intoSD59x18());
        } else {
            // if the market is not in the ADL state, it realizes the full requested USD Token amount
            market.updateNetUsdTokenIssuance(amountX18.intoSD59x18());
        }

        // loads the market making engine configuration storage pointer
        MarketMakingEngineConfiguration.Data storage marketMakingEngineConfiguration =
            MarketMakingEngineConfiguration.load();

        // mint USD Token to the perps engine
        UsdToken usdToken = UsdToken(marketMakingEngineConfiguration.usdTokenOfEngine[msg.sender]);
        usdToken.mint(msg.sender, amountToMint);

        // emit an event
        emit LogWithdrawUsdTokenFromMarket(msg.sender, marketId, amount, amountToMint);
    }
```
The vulnerability is located in the getCreditCapacityUsd function, which is used in the above function to calculate the market's credit capacity. See Market::getCreditCapacityUsd below:
```solidity
/// @notice Returns a market's credit capacity in USD based on its delegated credit and total debt.
    /// @param delegatedCreditUsdX18 The market's credit delegated by vaults in USD.
    /// @param totalDebtUsdX18 The market's unrealized + realized debt in USD.
    /// @return creditCapacityUsdX18 The market's credit capacity in USD.
    function getCreditCapacityUsd(
        UD60x18 delegatedCreditUsdX18,
        SD59x18 totalDebtUsdX18
    )
        internal
        pure
        returns (SD59x18 creditCapacityUsdX18)
    {
        creditCapacityUsdX18 = delegatedCreditUsdX18.intoSD59x18().add(totalDebtUsdX18);
    }
```
The incorrect logic is as follows:
```solidity
SD59x18 creditCapacityUsdX18 = Market.getCreditCapacityUsd(delegatedCreditUsdX18, marketTotalDebtUsdX18);
```
Incorrect Logic: Market::getCreditCapacityUsd function currently adds the total debt (marketTotalDebtUsdX18) to the delegated credit (delegatedCreditUsdX18). This is mathematically incorrect because:

Credit Capacity should represent the remaining capacity of the market to take on additional debt.

The correct formula should be: Credit Capacity = Delegated Credit - Total Debt

Overestimation of Credit Capacity: The current implementation overestimates the market's credit capacity, making it appear as though the market has more capacity to take on debt than it actually does.

For example:
Delegated Credit = 1000 USD
Total Debt = 300 USD
Correct Credit Capacity = 1000 - 300 = 700 USD
Bugged Credit Capacity = 1000 + 300 = 1300 USD

Unsafe System State: The system may allow withdrawals or minting of USD tokens even when the market does not have sufficient credit capacity to cover its liabilities. This could lead to insolvency if the market's debt exceeds its delegated credit.

Inconsistency with Vault::_updateCreditDelegations: Vault::_updateCreditDelegations function correctly calculates credit capacity by subtracting total debt from delegated credit. This inconsistency further highlights the bug in getCreditCapacityUsd. See below:
```solidity
/// @notice Updates the vault's credit delegations to its connected markets, using the provided cache of connected
    /// markets ids.
    /// @dev This function assumes that the connected markets ids cache is up to date with the stored markets ids. If
    /// this invariant resolves to false, the function will not work as expected.
    /// @dev We assume self.totalCreditDelegationWeight is always greater than zero, as it's verified during
    /// configuration.
    /// @param self The vault storage pointer.
    /// @param connectedMarketsIdsCache The cached connected markets ids.
    /// @param shouldRehydrateCache Whether the connected markets ids cache should be rehydrated or not.
    /// @return rehydratedConnectedMarketsIdsCache The potentially rehydrated connected markets ids cache.
    function _updateCreditDelegations(
        Data storage self,
        uint128[] memory connectedMarketsIdsCache,
        bool shouldRehydrateCache
    )
        private
        returns (uint128[] memory rehydratedConnectedMarketsIdsCache, SD59x18 vaultCreditCapacityUsdX18)
    {
        rehydratedConnectedMarketsIdsCache = new uint128[](connectedMarketsIdsCache.length);
        // cache the vault id
        uint128 vaultId = self.id;

        // cache the connected markets length
        uint256 connectedMarketsConfigLength = self.connectedMarkets.length;

        // loads the connected markets storage pointer by taking the last configured market ids uint set
        EnumerableSet.UintSet storage connectedMarkets = self.connectedMarkets[connectedMarketsConfigLength - 1];

        // loop over each connected market id that has been cached once again in order to update this vault's
        // credit delegations
        for (uint256 i; i < connectedMarketsIdsCache.length; i++) {
            // rehydrate the markets ids cache if needed
            if (shouldRehydrateCache) {
                rehydratedConnectedMarketsIdsCache[i] = connectedMarkets.at(i).toUint128();
            } else {
                rehydratedConnectedMarketsIdsCache[i] = connectedMarketsIdsCache[i];
            }

            // loads the memory cached market id
            uint128 connectedMarketId = rehydratedConnectedMarketsIdsCache[i];

            // load the credit delegation to the given market id
            CreditDelegation.Data storage creditDelegation = CreditDelegation.load(vaultId, connectedMarketId);

            // cache the previous credit delegation value
            UD60x18 previousCreditDelegationUsdX18 = ud60x18(creditDelegation.valueUsd);

            // cache the latest credit delegation share of the vault's credit capacity
            uint128 totalCreditDelegationWeightCache = self.totalCreditDelegationWeight;

            if (totalCreditDelegationWeightCache != 0) {
                // get the latest credit delegation share of the vault's credit capacity
                UD60x18 creditDelegationShareX18 =
                    ud60x18(creditDelegation.weight).div(ud60x18(totalCreditDelegationWeightCache));

                // stores the vault's total credit capacity to be returned
                vaultCreditCapacityUsdX18 = getTotalCreditCapacityUsd(self);

                // if the vault's credit capacity went to zero or below, we set its credit delegation to that market
                // to zero
                UD60x18 newCreditDelegationUsdX18 = vaultCreditCapacityUsdX18.gt(SD59x18_ZERO)
                    ? vaultCreditCapacityUsdX18.intoUD60x18().mul(creditDelegationShareX18)
                    : UD60x18_ZERO;

                // calculate the delta applied to the market's total delegated credit
                UD60x18 creditDeltaUsdX18 = newCreditDelegationUsdX18.sub(previousCreditDelegationUsdX18);

                // loads the market's storage pointer and update total delegated credit
                Market.Data storage market = Market.load(connectedMarketId);
                market.updateTotalDelegatedCredit(creditDeltaUsdX18);

                // if new credit delegation is zero, we clear the credit delegation storage
                if (newCreditDelegationUsdX18.isZero()) {
                    creditDelegation.clear();
                } else {
                    // update the credit delegation stored usd value
                    creditDelegation.valueUsd = newCreditDelegationUsdX18.intoUint1256x18();
                }
            }
        }
    }
```
The correct calculation is where the vaultCreditCapacityUsdX18 is calculated using Vault::getTotalCreditCapacityUsd. See function below:
```solidity
/// @notice Returns the vault's total credit capacity allocated to the connected markets.
    /// @dev The vault's total credit capacity is adjusted by its the credit ratio of its underlying collateral asset.
    /// @param self The vault storage pointer.
    /// @return creditCapacityUsdX18 The vault's total credit capacity in USD.
    function getTotalCreditCapacityUsd(Data storage self) internal view returns (SD59x18 creditCapacityUsdX18) {
        // load the collateral configuration storage pointer
        Collateral.Data storage collateral = self.collateral;

        // fetch the zlp vault's total assets amount
        UD60x18 totalAssetsX18 = ud60x18(IERC4626(self.indexToken).totalAssets());

        // calculate the total assets value in usd terms
        UD60x18 totalAssetsUsdX18 = collateral.getAdjustedPrice().mul(totalAssetsX18);

        // calculate the vault's credit capacity in usd terms
        creditCapacityUsdX18 = totalAssetsUsdX18.intoSD59x18().sub(getTotalDebt(self));
    }
```
As seen above, the credit capacity is calculated with Credit Capacity = Delegated Credit - Total Debt.

This vulnerability has a critical impact on the protocol's financial stability and security. Specifically:

Financial Losses: The protocol may allow withdrawals or minting of USD tokens beyond the market's actual capacity, leading to undercollateralization and potential insolvency.

System Instability: The incorrect credit capacity calculation could cause the system to operate in an unsafe state, where it cannot cover its liabilities.

Exploitation Risk: Malicious actors could exploit this bug to drain funds from the protocol by artificially inflating the market's credit capacity.

## Proof of Concept

```solidity
function test_creditcapacitywrongcalculation( 
        uint256 marketId,
        uint256 amount,
        uint256 amounttodepositcredit,
        uint128 vaultId,
        uint64 anyamount
    )
        external
    {
         amounttodepositcredit = bound({ x: amount, min: 1, max: type(uint32).max });

        PerpMarketCreditConfig memory fuzzMarketConfig = getFuzzPerpMarketCreditConfig(marketId);
       vaultId = uint128(bound(vaultId, INITIALVAULTID, FINALVAULTID));
        VaultConfig memory fuzzVaultConfig = getFuzzVaultConfig(vaultId);

        vm.assume(fuzzVaultConfig.asset != address(usdc));

        deal({ token: address(fuzzVaultConfig.asset), to: address(fuzzMarketConfig.engine), give: amounttodepositcredit*10 });
        changePrank({ msgSender: address(fuzzMarketConfig.engine) });

        // first user deposits credit into the market
        marketMakingEngine.depositCreditForMarket(fuzzMarketConfig.marketId, fuzzVaultConfig.asset, amounttodepositcredit);

        uint256 mmBalance = IERC20(fuzzVaultConfig.asset).balanceOf(address(marketMakingEngine));

        uint128 depositFee = uint128(vaultsConfig[fuzzVaultConfig.vaultId].depositFee);

        _setDepositFee(depositFee, fuzzVaultConfig.vaultId);

        // all code below makes the deposit into the vault that checks realized debt
        address user = users.naruto.account;
        deal(fuzzVaultConfig.asset, user, 100e18);

        // perform the deposit
        vm.startPrank(user);
        marketMakingEngine.deposit(vaultId, 1e18, 0, "", false);
        vm.stopPrank();

        vm.prank(address(fuzzMarketConfig.engine));
         marketMakingEngine.depositCreditForMarket(fuzzMarketConfig.marketId, fuzzVaultConfig.asset, amounttodepositcredit); 

        SD59x18 marketdebt = marketMakingEngine.workaround_getTotalMarketDebt(fuzzMarketConfig.marketId);
        console.log(marketdebt.unwrap());
       
      uint256 anyamount = bound(uint256(anyamount), 1, type(uint64).max);

        vm.prank(address(fuzzMarketConfig.engine));
         marketMakingEngine.withdrawUsdTokenFromMarket(fuzzMarketConfig.marketId, anyamount); 

          UD60x18 totaldelegatedcreditusd =  marketMakingEngine.workaround_getTotalDelegatedCreditUsd(fuzzMarketConfig.marketId); 
         console.log(totaldelegatedcreditusd.unwrap());

         SD59x18 expectedcreditcapacity = totaldelegatedcreditusd.intoSD59x18().sub(marketdebt);

          SD59x18 actualcreditcapacity = totaldelegatedcreditusd.intoSD59x18().add(marketdebt);

        // it should deposit credit for market
        assert(expectedcreditcapacity.unwrap() != actualcreditcapacity.unwrap());

    }
```

## Recommendation

```solidity
/// @notice Returns a market's credit capacity in USD based on its delegated credit and total debt.
    /// @param delegatedCreditUsdX18 The market's credit delegated by vaults in USD.
    /// @param totalDebtUsdX18 The market's unrealized + realized debt in USD.
    /// @return creditCapacityUsdX18 The market's credit capacity in USD.
    function getCreditCapacityUsd(
        UD60x18 delegatedCreditUsdX18,
        SD59x18 totalDebtUsdX18
    )
        internal
        pure
        returns (SD59x18 creditCapacityUsdX18)
    {
        creditCapacityUsdX18 = delegatedCreditUsdX18.intoSD59x18().sub(totalDebtUsdX18);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic error in the market credit‑capacity calculation used by CreditDelegationBranch::withdrawUsdTokenFromMarket. The function Market.getCreditCapacityUsd is supposed to return the remaining capacity of a market to take on additional debt, which mathematically is delegated credit minus total debt. The implementation mistakenly adds the total debt to the delegated credit, producing a credit‑capacity value that is larger than the true available capacity. Because withdrawUsdTokenFromMarket checks that this calculated credit capacity is greater than zero before minting USD tokens, the over‑estimated value allows the check to pass even when the market is actually under‑collateralised. An attacker can therefore call withdrawUsdTokenFromMarket with an arbitrarily large amount, causing the contract to mint USDz tokens that are not backed 1:1 by USDC. This breaks a core protocol invariant that every minted USD token must be fully collateralised, potentially leading to insolvency, loss of user funds, and systemic instability. The bug manifests whenever a live market with delegated credit processes a withdrawUsdTokenFromMarket call, regardless of whether the market is in auto‑deleverage mode. All participants that rely on the market’s USD token – traders, lenders, and token holders – are affected because the protocol may later be unable to honour redemptions or settlements. The issue was discovered during a manual audit by comparing the credit‑capacity logic in Market.getCreditCapacityUsd with the correct calculation performed in Vault::_updateCreditDelegations, which correctly subtracts debt from delegated credit. The mismatch is subtle because the function returns a signed integer that often remains positive, so the failure does not trigger an obvious revert and may be missed during routine testing. From a user perspective the symptom is that a withdrawal appears to succeed and the user receives a large amount of USDz, but later the protocol cannot provide the expected USDC backing, leading to missing refunds or zero balances when trying to redeem. The bug belongs to the class of “incorrect financial formula” or “credit‑capacity miscalculation” errors that violate accounting assumptions about available collateral. The recommended fix is to replace the addition with a subtraction in Market.getCreditCapacityUsd so that credit capacity = delegated credit – total debt, restoring the correct safety check before minting.
