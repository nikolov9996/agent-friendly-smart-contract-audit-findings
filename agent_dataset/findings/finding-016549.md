---
id: 16549
severity: "High"
---

# `LiquidationBranch::checkLiquidatableAccounts()` executes `for` loop with wrong values, causing array out of bounds to be recovered, the program will not work as expected

## Description

```solidity
    // LiquidationBranch::checkLiquidatableAccounts() 
    /// @param lowerBound The lower bound of the accounts to check
    /// @param upperBound The upper bound of the accounts to check
    function checkLiquidatableAccounts(
        uint256 lowerBound,
        uint256 upperBound
    )
        external
        view
        returns (uint128[] memory liquidatableAccountsIds)
    {
        // prepare output array size
        liquidatableAccountsIds = new uint128[](upperBound - lowerBound);

        // return if nothing to process
        if (liquidatableAccountsIds.length == 0) return liquidatableAccountsIds;

        // fetch storage slot for global config
        GlobalConfiguration.Data storage globalConfiguration = GlobalConfiguration.load();

        // cache active account ids length
        uint256 cachedAccountsIdsWithActivePositionsLength =
            globalConfiguration.accountsIdsWithActivePositions.length();

        // iterate over active accounts within given bounds
        for (uint256 i = lowerBound; i < upperBound; i++) {
            // break if i greater then length of active account ids
            if (i >= cachedAccountsIdsWithActivePositionsLength) break;

            // get the tradingAccountId of the current active account
            uint128 tradingAccountId = uint128(globalConfiguration.accountsIdsWithActivePositions.at(i));

            // load that account's leaf (data + functions)
            TradingAccount.Data storage tradingAccount = TradingAccount.loadExisting(tradingAccountId);

            // get that account's required maintenance margin & unrealized PNL
            (, UD60x18 requiredMaintenanceMarginUsdX18, SD59x18 accountTotalUnrealizedPnlUsdX18) =
                tradingAccount.getAccountMarginRequirementUsdAndUnrealizedPnlUsd(0, SD59x18_ZERO);

            // get that account's current margin balance
            SD59x18 marginBalanceUsdX18 = tradingAccount.getMarginBalanceUsd(accountTotalUnrealizedPnlUsdX18);

            // account can be liquidated if requiredMargin > marginBalance
            if (TradingAccount.isLiquidatable(requiredMaintenanceMarginUsdX18, marginBalanceUsdX18)) {
                liquidatableAccountsIds[i] = tradingAccountId;
            }
        }
    }
```
The length of the liquidatableAccountsIds array is upperBound - lowerBound, and this method can be used for segmented checking. But the starting value of the for loop is uint256 i = lowerBound. If lowerBound != 0, it is easy to recover due to array out of bounds.

Let's assume a scenario:
```solidity
upperBound = 10;
lowerBound = 20;
liquidatableAccountsIds = new uint128[](10);
for (uint256 i = lowerBound; i < upperBound; i++) {}
```
At this time, the maximum index of liquidatableAccountsIds is 9, but i = 10 in the first for loop, when the program executes to liquidatableAccountsIds[10] = tradingAccountId;, it will recover due to overflow.
And this method is called by LiquidationKeeper::checkUpkeep(), where different operations are performed according to the length of the array returned by LiquidationBranch::checkLiquidatableAccounts() (the code snippet is as follows).
```solidity
        uint128[] memory liquidatableAccountsIds =
            perpsEngine.checkLiquidatableAccounts(checkLowerBound, checkUpperBound);
        uint128[] memory accountsToBeLiquidated;

        if (liquidatableAccountsIds.length == 0 || liquidatableAccountsIds.length <= performLowerBound) {
            performData = abi.encode(accountsToBeLiquidated);

            return (upkeepNeeded, performData);
        }
```
However, due to the existence of the following code in LiquidationBranch::checkLiquidatableAccounts(), even if the conditions are not met, liquidatableAccountsIds[i] will default to 0. So we also need to clean up the objects with 0 in the liquidationAccountsIds array.
```solidity
            if (TradingAccount.isLiquidatable(requiredMaintenanceMarginUsdX18, marginBalanceUsdX18)) {
                liquidatableAccountsIds[i] = tradingAccountId;
            }
```

## Proof of Concept

Please add the test code to test/integration/perpetuals/liquidation-branch/checkLiquidatableAccounts/checkLiquidatableAccounts.t.sol and execute
```solidity
    function testcheckLiquidatableAccountserror() public {
        MarketConfig memory fuzzMarketConfig = getFuzzMarketConfig(1);  
        uint256 amountOfTradingAccounts = 30;
        uint256 marginValueUsd = 10_000e18 * 3 / amountOfTradingAccounts;
        uint256 initialMarginRate = fuzzMarketConfig.imr;
        bool isLong = true;
        deal({ token: address(usdz), to: users.naruto.account, give: marginValueUsd });

        for (uint256 i; i < amountOfTradingAccounts; i++) {
            uint256 accountMarginValueUsd = marginValueUsd / amountOfTradingAccounts;

            uint128 tradingAccountId = createAccountAndDeposit(accountMarginValueUsd, address(usdz));

            openPosition(fuzzMarketConfig, tradingAccountId, initialMarginRate, accountMarginValueUsd, isLong);
        }
        setAccountsAsLiquidatable(fuzzMarketConfig, isLong);
        uint256 lowerBound = 10;
        uint256 upperBound = 20;
        vm.expectRevert(abi.encodeWithSignature("Panic(uint256)", 0x32)); // panic: array out-of-bounds access (0x32)
        perpsEngine.checkLiquidatableAccounts(lowerBound, upperBound);
    }
    // Ran 1 test for test/integration/perpetuals/liquidation-branch/checkLiquidatableAccounts/checkLiquidatableAccounts.t.sol:CheckLiquidatableAccountsIntegrationTest
    // [PASS] testcheckLiquidatableAccountserror() (gas: 20435116)
```
Code Snippet
<https://github.com/Cyfrin/2024-07-zaros/blob/d687fe96bb7ace8652778797052a38763fbcbb1b/src/perpetuals/branches/LiquidationBranch.sol#L40-L86>
<https://github.com/Cyfrin/2024-07-zaros/blob/d687fe96bb7ace8652778797052a38763fbcbb1b/src/external/chainlink/keepers/liquidation/LiquidationKeeper.sol#L44-L88>

LiquidationBranch::checkLiquidatableAccounts() executes for loop with wrong values, causing array out of bounds to be recovered, the program will not work as expected

## Recommendation

Fix the revert caused by out-of-bounds i value in for loop
Clean up objects with value 0 in the liquidatableAccountsIds array

For example:
```diff
    /// @param lowerBound The lower bound of the accounts to check
    /// @param upperBound The upper bound of the accounts to check
    function checkLiquidatableAccounts(
        uint256 lowerBound,
        uint256 upperBound
    )
        external
        view
        returns (uint128[] memory liquidatableAccountsIds)
    {
        // prepare output array size
liquidatableAccountsIds = new uint128[](upperBound - lowerBound);
uint128] memory cacheLiquidatableAccountsIds = new uint128[;

        // return if nothing to process
if (liquidatableAccountsIds.length == 0) return liquidatableAccountsIds;
if (cacheLiquidatableAccountsIds.length == 0) return liquidatableAccountsIds;

        // fetch storage slot for global config
        GlobalConfiguration.Data storage globalConfiguration = GlobalConfiguration.load();

        // cache active account ids length
        uint256 cachedAccountsIdsWithActivePositionsLength =
            globalConfiguration.accountsIdsWithActivePositions.length();
uint256 count = 0; // Initialize count to keep track of valid entries
        // iterate over active accounts within given bounds
        for (uint256 i = lowerBound; i < upperBound; i++) {
            // break if i greater then length of active account ids
            if (i >= cachedAccountsIdsWithActivePositionsLength) break;

            // get the tradingAccountId of the current active account
            uint128 tradingAccountId = uint128(globalConfiguration.accountsIdsWithActivePositions.at(i));

            // load that account's leaf (data + functions)
            TradingAccount.Data storage tradingAccount = TradingAccount.loadExisting(tradingAccountId);

            // get that account's required maintenance margin & unrealized PNL
            (, UD60x18 requiredMaintenanceMarginUsdX18, SD59x18 accountTotalUnrealizedPnlUsdX18) =
                tradingAccount.getAccountMarginRequirementUsdAndUnrealizedPnlUsd(0, SD59x18_ZERO);

            // get that account's current margin balance
            SD59x18 marginBalanceUsdX18 = tradingAccount.getMarginBalanceUsd(accountTotalUnrealizedPnlUsdX18);

            // account can be liquidated if requiredMargin > marginBalance
            if (TradingAccount.isLiquidatable(requiredMaintenanceMarginUsdX18, marginBalanceUsdX18)) {
liquidatableAccountsIds[i] = tradingAccountId;
cacheLiquidatableAccountsIds[count] = tradingAccountId; // Use count as the index
count++; // Increment count for next valid entry
            }
        }
// Resize the array to remove trailing zeroes
liquidatableAccountsIds = new uint128[](count);
for (uint256 j = 0; j < count; j++) {
liquidatableAccountsIds[j] = cacheLiquidatableAccountsIds[j];   
}    
    }
```
test again,it's work.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the function that scans a range of trading accounts to determine which ones can be liquidated. The function allocates an output array whose length is the difference between the upper and lower bounds (upperBound‑lowerBound). However, the for‑loop that populates the array starts its counter at lowerBound and writes the result directly to liquidatableAccountsIds[i]. When lowerBound is greater than zero, the index i can be larger than the highest valid index of the newly created array (which is upperBound‑lowerBound‑1). As a result, the contract attempts to write to an out‑of‑bounds slot, causing the EVM to trigger a panic (error code 0x32) and revert the whole call. This bug was discovered during a security audit and confirmed with an integration test that deliberately supplies lowerBound = 10 and upperBound = 20, expecting the panic. The issue is subtle because the size of the array appears correct at allocation time, and the code does not contain an explicit bounds check before the write. From a user’s perspective the symptom is that the liquidation keeper receives an empty or zero‑filled list of liquidatable accounts, so positions that should be liquidated remain open, potentially leading to under‑collateralized accounts and loss of protocol safety. The affected parties include any trader whose position becomes under‑collateralized, liquidators who rely on the keeper to trigger liquidation, and the protocol itself because missed liquidations can erode capital reserves. The bug belongs to the class of array index out‑of‑bounds errors, a common source of runtime reverts in Solidity. It violates the business logic that the function should return a compact list of IDs; instead it either reverts or returns an array padded with default zeros. The exploit scenario is straightforward: an attacker (or even a benign caller) can invoke the function with a non‑zero lowerBound, causing the revert and preventing the keeper from performing any liquidation work. The fix consists of decoupling the external index from the internal array position, for example by using a separate counter (i‑lowerBound or an explicit count variable) when writing into liquidatableAccountsIds, and by trimming trailing zero entries after the loop. Additionally, the implementation should filter out zero values before the array is returned to the keeper. Applying these changes restores correct behaviour, prevents unexpected reverts, and ensures that liquidations are processed as intended.
