---
id: 23427
severity: "High"
---

# Arithmetic underflow in withdrawERC20 when there is a negative rebasing of asset tokens

## Description

The vault's accounting is based on the premise that the price of the underlying collateral will grow in perpetuity. While the underlying collateral has the lowest risks, capital is still susceptible to risk, especially when bonds are sold before maturity. For eg., if ONDO is ever forced to sell underlying bonds at market price and the bond's price is lower than the time they were purchased, that will cause a loss that will most likely mean a negative rebase on the price of USDY or oUSG.  

The vault tracks deposits using deposit-time pricing but calculates withdrawals using current market pricing. When prices decrease, the withdrawal calculation requires more tokens than the vault's accounting system has tracked as available.  

The consequences of a negative rebase (requiring more asset units for the same amount of USD) will impact the withdrawal flow when subtracting the withdrawAssetValue (and fee) from the VaultData.assetDepositNet, withdrawals will hit an underflow on that operation because the amount of asset units that will be discounted will be greater than the amount of asset units on the VaultData.assetDepositNet.  

```solidity
function withdrawERC20(
    address _to,
    YLD_Metadata memory MetaData
) external isValidIssuer {
    AssetDefinition memory AssetData = registry.fetchAssetData(assetID);
    // Calculate Withdraw asset value
    uint256 withdrawAssetValue = iSTBL_LT1_AssetOracle(AssetData.oracle)
        .fetchInversePrice(
            ((MetaData.stableValueNet + MetaData.haircutAmount) -
            MetaData.withdrawfeeAmount)
        ); //@audit gets the latest price -> if price is negative withdrawAssetValue can be greater
        // than assetDepositNet,!
    ...
    VaultData.assetDepositNet -= (withdrawAssetValue +
    withdrawFeeAssetValue); //@audit if the above happens, assetDepositNet will underflow
    ...
}
```

Impact: Potential denial of service on user withdrawals in the even of negative rebasing of asset prices.

## Proof of Concept

Add the following function to STBL_PT1_TestOracle:

```solidity
function decreasePriceByPercentage(uint256 basisPoints) external {
    require(basisPoints <= 9999, "Cannot decrease more than 99.99%");
    price = (price * (10000 - basisPoints)) / 10000;
}
```

Then add the following test to STBL_Test.sol:

```solidity
/// @notice Test deposit -> large price decrease -> attempted yield distribution -> withdrawal
/// @dev This tests accounting integrity under negative price movements and potential underflow
risks,!
function test_DepositWithdraw1PctPriceDecrease() public {
    console.log("=== 1% PRICE DECREASE TEST ===");
    // Get contracts
    STBL_PT1_TestToken assetToken = STBL_PT1_TestToken(getAssetToken(1));
    STBL_PT1_Issuer stblPT1Issuer = STBL_PT1_Issuer(getAssetIssuer(1));
    STBL_PT1_Vault stblPT1Vault = STBL_PT1_Vault(getAssetVault(1));
    STBL_PT1_TestOracle stblPT1TestOracle = STBL_PT1_TestOracle(getAssetOracle(1));
    STBL_PT1_YieldDistributor yieldDist = STBL_PT1_YieldDistributor(getAssetYieldDistributor(1));
    // === PHASE 0: ENSURE VAULT LIQUIDITY ===
    // Add significant extra tokens directly to vault to ensure liquidity
    // This prevents withdrawal failures due to insufficient vault balance after price drop
    console.log("--- PHASE 0: ENSURE VAULT LIQUIDITY ---");
    uint256 extraLiquidity = 100000e6; // 100,000 extra tokens
    vm.startPrank(admin);
    assetToken.mintVal(address(stblPT1Vault), extraLiquidity);
    vm.stopPrank();
    // Setup treasury
    vm.startPrank(admin);
    registry.setTreasury(admin);
    vm.stopPrank();
    // === PHASE 1: INITIAL DEPOSIT ===
    console.log("--- PHASE 1: DEPOSIT ---");
    uint256 depositAmount = 10000e6;
    vm.startPrank(user1);
    assetToken.approve(address(stblPT1Vault), depositAmount);
    uint256 nftId = stblPT1Issuer.deposit(depositAmount);
    vm.stopPrank();
    // Log initial state
    console.log("Initial deposit NFT ID:", nftId);
    console.log("Initial oracle price:", stblPT1TestOracle.fetchPrice());
    console.log("Initial vault token balance:", assetToken.balanceOf(address(stblPT1Vault)));
    console.log("User USST balance:", usst.balanceOf(user1));
    // Get initial metadata and vault state
    YLD_Metadata memory initialMetadata = yld.getNFTData(nftId);
    VaultStruct memory initialVaultData = stblPT1Vault.fetchVaultData();
    console.log("Asset value:", initialMetadata.assetValue);
    console.log("Stable value net:", initialMetadata.stableValueNet);
    console.log("Initial vault asset deposit net:", initialVaultData.assetDepositNet);
    console.log("Initial vault deposit value USD:", initialVaultData.depositValueUSD);
    // === PHASE 2: ADVANCE TIME FOR YIELD ELIGIBILITY ===
    console.log("\n--- PHASE 2: ADVANCE TIME FOR YIELD ELIGIBILITY ---");
    vm.warp(block.timestamp + initialMetadata.Fees.yieldDuration + 1);
    console.log("Advanced time by:", initialMetadata.Fees.yieldDuration + 1, "seconds");
    // === PHASE 3: LARGE PRICE DECREASE ===
    console.log("\n--- PHASE 3: LARGE PRICE DECREASE ---");
    uint256 initialPrice = stblPT1TestOracle.fetchPrice();
    console.log("Price before decrease:", initialPrice);
    // Simulate 10% price decrease
    stblPT1TestOracle.decreasePriceByPercentage(100);
    uint256 newPrice = stblPT1TestOracle.fetchPrice();
    console.log("Price after decrease:", newPrice);
    console.log("Percentage change:", stblPT1TestOracle.calculatePercentageChange(initialPrice,
    newPrice));,!
    // === PHASE 4: CHECK YIELD CALCULATION AFTER PRICE DECREASE ===
    console.log("\n--- PHASE 4: YIELD CALCULATION AFTER PRICE DECREASE ---");
    // Check vault state before potential yield distribution
    VaultStruct memory preYieldVaultData = stblPT1Vault.fetchVaultData();
    console.log("Vault asset deposit net (pre-yield attempt):", preYieldVaultData.assetDepositNet);
    console.log("Vault deposit value USD (pre-yield attempt):", preYieldVaultData.depositValueUSD);
    // Calculate price differential - should be 0 for price decrease
    uint256 priceDifferential = stblPT1Vault.CalculatePriceDifferentiation();
    console.log("Price differential calculated:", priceDifferential);
    // Verify that no yield is distributed when price decreases
    assertEq(priceDifferential, 0, "Price differential should be 0 when price decreases");
    // Attempt yield distribution - should be a no-op
    vm.startPrank(admin);
    stblPT1Vault.distributeYield();
    vm.stopPrank();
    // Check vault state after yield distribution attempt
    VaultStruct memory postYieldVaultData = stblPT1Vault.fetchVaultData();
    console.log("Vault asset deposit net (post-yield attempt):",
    postYieldVaultData.assetDepositNet);,!
    console.log("Vault yield fees collected:", postYieldVaultData.yieldFees);
    // Verify no changes occurred during yield distribution
    assertEq(postYieldVaultData.assetDepositNet, preYieldVaultData.assetDepositNet, "assetDepositNet
    should not change");,!
    assertEq(postYieldVaultData.yieldFees, preYieldVaultData.yieldFees, "yieldFees should not
    change");,!
    // === PHASE 5: WITHDRAWAL UNDER DECREASED PRICE CONDITIONS ===
    console.log("\n--- PHASE 5: WITHDRAWAL UNDER DECREASED PRICE ---");
    // Check if user can still withdraw when asset price has decreased
    uint256 usstBalance = usst.balanceOf(user1);
    console.log("USST balance before withdrawal:", usstBalance);
    vm.startPrank(user1);
    usst.approve(address(usst), usstBalance);
    yld.setApprovalForAll(address(yld), true);
    uint256 preWithdrawVaultBalance = assetToken.balanceOf(address(vault));
    uint256 preWithdrawUserBalance = assetToken.balanceOf(user1);
    console.log("Vault balance before withdrawal:", preWithdrawVaultBalance);
    console.log("User balance before withdrawal:", preWithdrawUserBalance);
    // Attempt withdrawal
    vm.expectRevert();
    stblPT1Issuer.withdraw(nftId, user1);
    vm.stopPrank();
}
```

## Recommendation

Consider modifying withdrawERC20 to prevent underflows by capping withdrawals to available accounting balance:

```solidity
function withdrawERC20(address _to, YLD_Metadata memory MetaData) external isValidIssuer {
    AssetDefinition memory AssetData = registry.fetchAssetData(assetID);
    uint256 withdrawAssetValue = iSTBL_PT1_AssetOracle(AssetData.oracle)
        .fetchInversePrice(
            ((MetaData.stableValueNet + MetaData.haircutAmount) - MetaData.withdrawfeeAmount)
        );
    uint256 withdrawFeeAssetValue = iSTBL_PT1_AssetOracle(AssetData.oracle)
        .fetchInversePrice(MetaData.withdrawfeeAmount);
    uint256 totalWithdrawal = withdrawAssetValue + withdrawFeeAssetValue;
    // @audit Cap withdrawal to available balance
    if (VaultData.assetDepositNet < totalWithdrawal) {
        uint256 availableWithdrawal = VaultData.assetDepositNet > withdrawFeeAssetValue
            ? VaultData.assetDepositNet - withdrawFeeAssetValue
            : 0;
        withdrawAssetValue = availableWithdrawal;
        VaultData.assetDepositNet = 0; //@audit effectively force this to 0
    } else {
        VaultData.assetDepositNet -= totalWithdrawal;
    }
    // Rest of function continues normally...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic underflow in the withdrawERC20 function of a vault contract that occurs when the underlying collateral experiences a negative price rebase. The vault’s accounting model assumes that the price of the collateral only increases, so deposits are recorded using the price at deposit time while withdrawals are calculated using the current market price. When the price drops, the inverse price used to convert the stable value back into the asset rises, causing the computed withdrawAssetValue (plus any fee) to exceed the vault’s stored assetDepositNet. The subtraction VaultData.assetDepositNet -= (withdrawAssetValue + withdrawFeeAssetValue) then underflows, wrapping around to a very large number and triggering a transaction revert. This underflow prevents the transfer of tokens, resulting in a denial‑of‑service for user withdrawals whenever a negative rebase occurs. The issue was discovered during a security audit that included a test oracle capable of decreasing the price by a percentage; the test demonstrated that after a 10 % price drop the withdrawal call reverted as expected. The bug is hard to notice because the contract appears to work correctly under normal price‑appreciation scenarios, and the revert only surfaces under specific market conditions that may be rare in production. From a user’s perspective the UI may show a zero or unchanged balance after attempting a withdrawal, or a pending transaction that never delivers tokens, leading to confusion and panic. The impact violates the business logic that users should be able to redeem their stable value for the underlying asset at any time, breaking the accounting invariant that assetDepositNet always covers withdrawals. The affected parties include all depositors, the protocol’s liquidity providers, and any downstream applications that rely on reliable withdrawals. To remediate, the withdrawal logic should be modified to cap the withdrawal amount to the available assetDepositNet, ensuring that the subtraction never underflows. Conceptually, this means adding a check that if the calculated total withdrawal exceeds the net deposit, the contract either reduces the withdrawal to the maximum allowable amount or rejects the operation with a clear error, thereby preserving accounting integrity and preventing denial‑of‑service.
