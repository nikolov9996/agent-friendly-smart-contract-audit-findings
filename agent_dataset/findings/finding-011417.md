---
id: 11417
severity: "Medium"
---

# Incorrect weight assignment in Vault::updateVaultAndCreditDelegationWeight leads to overleveraging vault positions and insolvency

## Description

A critical vulnerability exists in the Vault::updateVaultAndCreditDelegationWeight, where the weight assigned to each connected market is incorrectly set to the total assets of the vault instead of a proportional share. This results in the total delegated credit across all markets exceeding the vault's total assets, leading to overleveraging and potential insolvency.

Vault::updateVaultAndCreditDelegationWeight is called in Vault::Vault::recalculateVaultsCreditCapacity and its job is to set weights of each connected market proportional to the total weight of the vault. See function below:

```solidity
  /// @notice Update the vault and credit delegation weight
    /// @param self The vault storage pointer.
    /// @param connectedMarketsIdsCache The cached connected markets ids.
    function updateVaultAndCreditDelegationWeight(
        Data storage self,
        uint128[] memory connectedMarketsIdsCache
    )
        internal
    {
        // cache the connected markets length
        uint256 connectedMarketsConfigLength = self.connectedMarkets.length;

        // loads the connected markets storage pointer by taking the last configured market ids uint set
        EnumerableSet.UintSet storage connectedMarkets = self.connectedMarkets[connectedMarketsConfigLength - 1];

        // get the total of shares
        uint128 newWeight = uint128(IERC4626(self.indexToken).totalAssets());

        for (uint256 i; i < connectedMarketsIdsCache.length; i++) {
            // load the credit delegation to the given market id
            CreditDelegation.Data storage creditDelegation =
                CreditDelegation.load(self.id, connectedMarkets.at(i).toUint128());

            // update the credit delegation weight
            creditDelegation.weight = newWeight;
        }

        // update the vault weight
        self.totalCreditDelegationWeight = newWeight;
    }
```

The function assigns the total assets of the vault (newWeight) to each connected market individually:

```solidity
creditDelegation.weight = newWeight;
```

If there are multiple connected markets, each market is assigned the full weight of the vault, leading to an overestimation of the total delegated credit.

Example:
Vault Total Assets = 1000 wETH
Connected Markets = 2
Each market is assigned a weight of 1000 wETH.

Total delegated credit = 1000 + 1000 = 2000 wETH (exceeds the vault's total assets).

Overleveraging: The total delegated credit across all markets exceeds the vault's total assets, putting the system in an overleveraged and unsafe state.

Financial Instability: If one or more markets face losses, the vault may not have enough assets to cover the losses, leading to insolvency.

Exploitation Risk: Malicious actors could exploit this bug to overleverage the system, resulting in significant financial losses.

Loss of User Funds: Users who deposit collateral into the vault may lose their funds if the vault becomes insolvent due to overleveraging.

## Proof of Concept

```solidity
function testFuzz_marketweightsharescalculationerror(
        uint256 vaultId1,
        uint256 marketId1,
        uint256 vaultId2,
        uint256 marketId2
    )
        external
    {
        vm.stopPrank();
        VaultConfig memory fuzzVaultConfig1 = getFuzzVaultConfig(vaultId1);
         vm.assume(fuzzVaultConfig1.asset != address(usdc));
        PerpMarketCreditConfig memory fuzzMarketConfig1 = getFuzzPerpMarketCreditConfig(marketId1);

         VaultConfig memory fuzzVaultConfig2 = getFuzzVaultConfig(vaultId2);
         vm.assume(fuzzVaultConfig2.asset != address(usdc));
        PerpMarketCreditConfig memory fuzzMarketConfig2 = getFuzzPerpMarketCreditConfig(marketId2);
        vm.assume(fuzzMarketConfig1.marketId != fuzzMarketConfig2.marketId);
        vm.assume(fuzzVaultConfig1.vaultId != fuzzVaultConfig2.vaultId);

        //c set up 2 vaults and connect them to 2 markets
        uint256[] memory marketIds = new uint256[](2);
        marketIds[0] = fuzzMarketConfig1.marketId;
        marketIds[1] = fuzzMarketConfig2.marketId;

        uint256[] memory vaultIds = new uint256[](2);
        vaultIds[0] = fuzzVaultConfig1.vaultId;
        vaultIds[1] = fuzzVaultConfig2.vaultId;

        vm.prank(users.owner.account);
        marketMakingEngine.connectVaultsAndMarkets(marketIds, vaultIds);

          address user = users.naruto.account;
        deal(fuzzVaultConfig1.asset, user, 100e18);
        deal(fuzzVaultConfig2.asset, user, 100e18);

        //c deposit assets into both vaults so that each vaults credit capacity is 1e18 which gives each market a totalcreditdelegatedweight of 2e18 which is where the bug is.

        //c have to deposit twice because updates from Vault::recalculateVaultsCreditCapacity when called in VaultRouterBranch::deposit is called at the start so the deposited collateral isnt reflected . could have also called CreditDelegationBranch::updateVaultCreditCapacity but I chose this way instead

        vm.startPrank(user);
        marketMakingEngine.deposit(fuzzVaultConfig1.vaultId, 1e18, 0, "", false);
        marketMakingEngine.deposit(fuzzVaultConfig1.vaultId, 1e18, 0, "", false);
        marketMakingEngine.deposit(fuzzVaultConfig2.vaultId, 1e18, 0, "", false);
        marketMakingEngine.deposit(fuzzVaultConfig2.vaultId, 1e18, 0, "", false);
        vm.stopPrank();
       
        //c deposit credit of 2e18 into both markets so totaldelegatedcredit of both markets is 4e18 which is more than the credit capacity of both vaults. this proves that the market is allocated more credit than the vault can handle which leaves zaros in an overleveraged position
        deal({ token: address(fuzzVaultConfig1.asset), to: address(fuzzMarketConfig1.engine), give: 10e18 });
        deal({ token: address(fuzzVaultConfig2.asset), to: address(fuzzMarketConfig2.engine), give: 10e18 });
        vm.prank( address(fuzzMarketConfig1.engine));
        marketMakingEngine.depositCreditForMarket(fuzzMarketConfig1.marketId, fuzzVaultConfig1.asset, 2e18);
        vm.prank( address(fuzzMarketConfig2.engine));
        marketMakingEngine.depositCreditForMarket(fuzzMarketConfig2.marketId, fuzzVaultConfig2.asset, 2e18);

        //c get the totalmarketdebt of each market in usd
        uint256 totalmarketdebt;
        for(uint i = 0; i < marketIds.length; i++){
            SD59x18 marketdebt = marketMakingEngine.workaround_getTotalMarketDebt(uint128(marketIds[i]));
            console.log(marketdebt.unwrap());
            totalmarketdebt += uint256(marketdebt.unwrap());
        }
        console.log(totalmarketdebt);

        /*c get the total asset value in usd. to do this, i included the following function in vault.sol.
        //c for testing purposes
    function getTotalAssetsUsd(Data storage self) internal view returns (UD60x18 totalAssetsUsdX18) {
        // load the collateral configuration storage pointer
        Collateral.Data storage collateral = self.collateral;

        // fetch the zlp vault's total assets amount
        UD60x18 totalAssetsX18 = ud60x18(IERC4626(self.indexToken).totalAssets());

        // calculate the total assets value in usd terms
         totalAssetsUsdX18 = collateral.getAdjustedPrice().mul(totalAssetsX18);

        I also included this function in VaultRouterBranch.sol:
        //c for testing purposes
    function gettotalassetsusd(uint128 vaultId) external view returns (uint256) {
        Vault.Data storage vault = Vault.loadLive(vaultId);
        return vault.getTotalAssetsUsd().intoUint256();
    }   

    After registering the selector of this function in TreeProxyUtils.sol, it should work as expected

        */
        uint256 totalassetvalue;
        for (uint i = 0; i< vaultIds.length; i++){
            uint256 assetvalueusd = marketMakingEngine.gettotalassetsusd(uint128(vaultIds[i]));
        totalassetvalue += assetvalueusd;
        }
        console.log(totalassetvalue);

        //c shows that the total usd value of the debt after perpengine has called CreditDelegationBranch::depositCreditForMarket is more than the total usd value of the assets in the vaults which proves that zaros will be overleveraged
        assert(totalmarketdebt > totalassetvalue);

        //c I have not included the call to CreditDelegationBranch::withdrawUsdTokenFromMarket because as I explained in my previous finding, there is a bug also in that function that allows any user to bypass the creditcapacity check and withdraw any amount of usdz so that wouldn't necessarily prove anything. 

}
```

## Recommendation

Update Vault::updateVaultAndCreditDelegationWeight function to assign a proportional share of the vault's total assets to each connected market. This can be achieved by dividing the vault's total assets by the number of connected markets.

```solidity
 function updateVaultAndCreditDelegationWeight(
        Data storage self,
        uint128[] memory connectedMarketsIdsCache
    )
        internal
    {
        // cache the connected markets length
        uint256 connectedMarketsConfigLength = self.connectedMarkets.length;

        // loads the connected markets storage pointer by taking the last configured market ids uint set
        EnumerableSet.UintSet storage connectedMarkets = self.connectedMarkets[connectedMarketsConfigLength - 1];

        // get the total of shares
        uint128 newWeight = uint128(IERC4626(self.indexToken).totalAssets());

          // Calculate the weight per market
          uint128 weightPerMarket = newWeight / uint128(connectedMarketsIdsCache.length);

          for (uint256 i; i < connectedMarketsIdsCache.length; i++) {
         // Load the credit delegation to the given market id
         CreditDelegation.Data storage creditDelegation =
         CreditDelegation.load(self.id, connectedMarkets.at(i).toUint128());

        // Update the credit delegation weight
          creditDelegation.weight = weightPerMarket;
          }

       // update the vault weight
        self.totalCreditDelegationWeight = newWeight;
    }
```

Add a check to ensure that the number of connected markets is greater than zero before dividing.

```solidity
require(connectedMarketsIdsCache.length > 0, "No connected markets");
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect allocation of credit delegation weight inside the vault contract. When the vault updates the weight for each connected market, it assigns the vault's total asset amount to every market instead of dividing that amount among the markets. This root‑cause stems from using the totalAssets value as a constant newWeight and writing it directly to each CreditDelegation.weight entry without scaling it by the number of markets. The bug is triggered whenever a vault has more than one connected market and the function updateVaultAndCreditDelegationWeight is invoked during the recalculation of the vault's credit capacity. An attacker can exploit the flaw by connecting multiple markets to a single vault; each market receives a weight equal to the full vault balance, so the sum of delegated credit across markets can be twice, three‑times, or more than the actual assets held. The resulting overleveraging means the protocol may allocate credit that it cannot back, leading to a situation where market losses cannot be covered by the vault, potentially causing insolvency. Users who have deposited collateral may see their balances unexpectedly drop to zero, withdrawals fail, or refunds disappear because the vault no longer holds sufficient assets to satisfy claims. The issue was discovered by the CodeHawks audit team through a fuzzing test that demonstrated total delegated credit exceeding total vault assets. It is hard to notice because each individual market weight appears correct in isolation, and there is no explicit check that the aggregate weight stays within the vault's asset limit. Conceptually, the bug belongs to the class of proportional allocation errors where a shared resource is duplicated instead of being split, violating the fundamental accounting invariant that total delegated credit must never exceed total assets. To remediate, the contract should compute a per‑market weight as totalAssets divided by the number of connected markets, ensure the divisor is non‑zero, and update each CreditDelegation.weight with this proportional value. This restores the invariant and prevents overleveraging of vault positions.
