---
id: 25073
severity: "Medium"
---

# Cannot repay or liquidate on paused asset

## Description



## Proof of Concept

```solidity
pragma solidity ^0.8.28;

import { IOracle } from "../contracts/interfaces/IOracle.sol";
import { TestDeployer } from "./deploy/TestDeployer.sol";
import { console } from "forge-std/console.sol";

contract POC is TestDeployer {
    address user_agent;

    function setUp() public {
        _deployCapTestEnvironment();

        _initTestVaultLiquidity(usdVault);
        _initSymbioticVaultsLiquidity(env);

        user_agent = _getRandomAgent();

        vm.startPrank(env.symbiotic.users.vault_admin);
        _symbioticVaultDelegateToAgent(symbioticWethVault, env.symbiotic.networkAdapter, user_agent, 100e18);
        vm.stopPrank();
    }

    function test_submissionValidity() public {
        _setAssetOraclePrice(address(weth), 2000e8);
        vm.startPrank(user_agent);
        lender.borrow(address(usdc), 11000e6, user_agent);
        vm.stopPrank();

        vm.startPrank(env.users.access_control_admin);
        accessControl.grantAccess(lender.pauseAsset.selector, address(lender), env.users.vault_config_admin);
        vm.stopPrank();

        vm.startPrank(env.users.vault_config_admin);
        cUSD.pauseAsset(address(usdc));
        lender.pauseAsset(address(usdc), true);
        vm.stopPrank();

        vm.startPrank(user_agent);
        _timeTravel(90 days);
        usdc.approve(address(lender), 5000e6);

        vm.expectRevert(abi.encodeWithSignature("AssetPaused(address)", address(usdc)));
        lender.repay(address(usdc), 5000e6, user_agent);
        vm.stopPrank();
    }
}
```

## Recommendation

```diff
diff --git a/cap-contracts/contracts/lendingPool/libraries/BorrowLogic.sol b/cap-contracts/contracts/lendingPool/libraries/BorrowLogic.sol
index 3c2b60a..e36f043 100644
--- a/cap-contracts/contracts/lendingPool/libraries/BorrowLogic.sol
+++ b/cap-contracts/contracts/lendingPool/libraries/BorrowLogic.sol
@@ -214,8 +214,10 @@ library BorrowLogic {
         reserve.totalUnrealizedInterest += unrealizedInterest;

         IDebtToken(reserve.debtToken).mint(_agent, realizedInterest + unrealizedInterest);
-        IVault(reserve.vault).borrow(_asset, realizedInterest, $.delegation);
-        IDelegation($.delegation).distributeRewards(_agent, _asset);
+        if (realizedInterest > 0) {
+            IVault(reserve.vault).borrow(_asset, realizedInterest, $.delegation);
+            IDelegation($.delegation).distributeRewards(_agent, _asset);
+        }
         emit RealizeInterest(_asset, realizedInterest, $.delegation);
     }

```

After applying the patch, run the POC again to see if repayment on paused asset is possible.
