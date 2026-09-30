---
id: 4982
severity: "High"
---

# Incorrect Asset Redemption in Vault Withdrawal Leading to Loss of Funds Submitted by mohitisimmortal, also found by Nyksx and Joshuajee

## Description

When a user withdraws funds from the vault and the vault's immediate asset balance is less than the withdrawal request, the withdrawal function enters the else branch of OrderManager.sol::withdrawAssets(). Instead of transferring the entire requested amount, it subtracts the vault's balance from the requested amount, and only transfers the redeemed shortfall from the orders. Consequently, the user receives less than expected. Moreover, the vault burns shares for the full withdrawal amount, causing the user's position to be reduced improperly, and further withdrawal attempts fail with ERC4626ExceededMaxWithdraw.
Working of OrderManager.sol::withdrawAssets():
1. First, the function checks if the vault's own asset balance is suﬃcient to cover the withdrawal. If yes, it transfers the amount directly.
2. If Not: go to else condition:
• It calculates amountLeft = amount - assetBalance (the shortfall).
• Then, it iterates over the _withdrawQueue to redeem assets from orders to cover the shortfall.
• Then transfers those amountLeft to users.
In OrderManager.sol::withdrawAssets():
```solidity
amountLeft -= assetBalance;
} else {
    asset.safeTransfer(recipient, amountLeft);
    amountLeft = 0;
    break;
} else {
    _burnFromOrder(ITermMaxOrder(order), orderInfo, amountLeft);
    asset.safeTransfer(recipient, amountLeft);
    amountLeft = 0;
    break;
}
```
It never transfer those assetBalance amount but subtract it and then only transfers amountLeft.

Impact Explanation:
High:
- Underpayment: Users will receive only the `shortfall (requested amount minus vault's balance)` rather than the full requested withdrawal amount.
- Asset Loss: Since shares corresponding to the full withdrawal are burned, users permanently loose the untransferred portion.
- Subsequent Withdrawal Failure: The user's share balance is reduced to reflect the full withdrawal, making future withdrawal attempts fail due to insufficient redeemable assets. Transaction will revert with error-`ERC4626ExceededMaxWithdraw`.

## Proof of Concept

1. Add test into repo's test folder (Shortfall.t.sol), most of the setup is mimcked from Protocol's test/TermMaxTestBase.t.sol:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;
import "forge-std/Test.sol";
import {console} from "forge-std/console.sol";
import {DeployUtils} from "./utils/DeployUtils.sol";
import {JSONLoader} from "./utils/JSONLoader.sol";
import {StateChecker} from "./utils/StateChecker.sol";
import {SwapUtils} from "./utils/SwapUtils.sol";
import {LoanUtils} from "./utils/LoanUtils.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";
import {IFlashLoanReceiver} from "contracts/IFlashLoanReceiver.sol";
import {ITermMaxMarket, TermMaxMarket, Constants, MarketEvents, MarketErrors} from "contracts/TermMaxMarket.sol";
import {ITermMaxOrder, TermMaxOrder, ISwapCallback, OrderEvents, OrderErrors} from "contracts/TermMaxOrder.sol";
import {MockERC20, ERC20} from "contracts/test/MockERC20.sol";
import {MockPriceFeed} from "contracts/test/MockPriceFeed.sol";
import {TermMaxVault} from "contracts/vault/TermMaxVault.sol";
import {VaultErrors, VaultEvents, ITermMaxVault} from "contracts/vault/TermMaxVault.sol";
import {OrderManager} from "contracts/vault/OrderManager.sol";
import {VaultConstants} from "contracts/lib/VaultConstants.sol";
import {PendingAddress, PendingUint192} from "contracts/lib/PendingLib.sol";
import {MockSwapAdapter} from "contracts/test/MockSwapAdapter.sol";
import {SwapUnit, ISwapAdapter} from "contracts/router/ISwapAdapter.sol";
import {RouterErrors, RouterEvents, TermMaxRouter} from "contracts/router/TermMaxRouter.sol";
import "contracts/storage/TermMaxStorage.sol";
contract Shortfall is Test {
    using JSONLoader for *;
    using SafeCast for *;
    address user1 = vm.randomAddress();
    address user2 = vm.randomAddress();
    DeployUtils.Res res;
    OrderConfig orderConfig;
    MarketConfig marketConfig;
    address admin = vm.randomAddress();
    address curator = vm.randomAddress();
    address allocator = vm.randomAddress();
    address guardian = vm.randomAddress();
    address treasurer = vm.randomAddress();
    string testdata;
    ITermMaxVault vault;
    uint256 timelock = 86400;
    uint256 maxCapacity = 1000000e18;
    uint64 performanceFeeRate = 0.5e8;
    ITermMaxMarket market2;
    uint256 currentTime;
    uint32 maxLtv = 0.89e8;
    uint32 liquidationLtv = 0.9e8;
    VaultInitialParams initialParams;
    address pool = vm.randomAddress();
    MockSwapAdapter adapter;

    function setUp() public {
        vm.startPrank(admin);
        testdata = vm.readFile(string.concat(vm.projectRoot(), "/test/testdata/testdata.json"));
        currentTime = vm.parseUint(vm.parseJsonString(testdata, ".currentTime"));
        vm.warp(currentTime);
        marketConfig = JSONLoader.getMarketConfigFromJson(treasurer, testdata, ".marketConfig");
        orderConfig = JSONLoader.getOrderConfigFromJson(testdata, ".orderConfig");
        marketConfig.maturity = uint64(currentTime + 90 days);
        res = DeployUtils.deployMockMarket(admin, marketConfig, maxLtv, liquidationLtv);
        MarketConfig memory marketConfig2 = JSONLoader.getMarketConfigFromJson(treasurer, testdata, ".marketConfig");
        marketConfig2.maturity = uint64(currentTime + 180 days);
        market2 = ITermMaxMarket(
            res.factory.createMarket(
                DeployUtils.GT_ERC20,
                MarketInitialParams({
                    collateral: address(res.collateral),
                    debtToken: res.debt,
                    admin: admin,
                    gtImplementation: address(0),
                    marketConfig: marketConfig2,
                    loanConfig: LoanConfig({
                        maxLtv: maxLtv,
                        liquidationLtv: liquidationLtv,
                        liquidatable: true,
                        oracle: res.oracle
                    }),
                    gtInitalParams: abi.encode(type(uint256).max),
                    tokenName: "test",
                    tokenSymbol: "test"
                }),
            )
        );
        // update oracle
        res.collateralOracle.updateRoundData(
            JSONLoader.getRoundDataFromJson(testdata, ".priceData.ETH_2000_DAI_1.eth")
        );
        res.debtOracle.updateRoundData(JSONLoader.getRoundDataFromJson(testdata, ".priceData.ETH_2000_DAI_1.dai"));
        initialParams = VaultInitialParams(
            admin,
            curator,
            timelock,
            res.debt,
            maxCapacity,
            "Vault-DAI",
            "Vault-DAI",
            performanceFeeRate
        );
        res.vault = DeployUtils.deployVault(initialParams);
        vm.stopPrank();
        vm.startPrank(user1);
        res.debt.mint(user1, 1000e8);
        res.debt.approve(address(res.vault), 1000e8);
        res.vault.deposit(1000e8, user1);
        vm.stopPrank();
        vm.startPrank(admin);
        res.vault.submitGuardian(guardian);
        res.vault.setIsAllocator(allocator, true);
        res.vault.submitMarket(address(res.market), true);
        vm.warp(currentTime + timelock + 1);
        res.vault.acceptMarket(address(res.market));
        vm.warp(currentTime);
        res.order = res.vault.createOrder(res.market, maxCapacity, 0, orderConfig.curveCuts);
        res.router = DeployUtils.deployRouter(admin);
        res.router.setMarketWhitelist(address(res.market), true);
        adapter = new MockSwapAdapter(pool);
        res.router.setAdapterWhitelist(address(adapter), true);
        vm.stopPrank();
    }

    function testFail_WithdrawShortfallBug() public {
        vm.startPrank(user2);
        res.debt.mint(user2, 1200e8);
        res.debt.approve(address(res.vault), 1200e8);
        // User2 deposits 1200 tokens.
        res.vault.deposit(1200e8, user2);
        vm.stopPrank();
        uint256 requestWithdraw = 1200e8; // user2 requests to withdraw 1200 tokens
        // Perform withdrawal as user.
        vm.prank(user2);
        res.vault.withdraw(requestWithdraw, user2, user2);
        console.log("User attempted to withdraw:", requestWithdraw / 1e8);
        console.log("Withdrawn amount returned:", res.debt.balanceOf(user2) / 1e8);
        // Even user only gets 200 tokens but, vault burned shares for the full 1200 tokens
        // Now, if the user attempts another withdrawal to get their leftout tokens(1200-200 = 1000 leftout tokens), it should revert. Effectively loose their 1000 tokens.
        vm.prank(user2);
        res.vault.withdraw(100e8, user2, user2);
    }
}
```
2. Run forge test Shortfall.t.sol -vv.
3. Output:
[PASS] testFail_WithdrawShortfallBug() (gas: 602027)
Logs:
User attempted to withdraw: 1200
Withdrawn amount returned: 200
• The test logs show that the user receives significantly less tokens than his requested amount, and subsequent withdrawal attempts revert with ERC4626ExceededMaxWithdraw.
• To see that ERC4626ExceededMaxWithdraw error, run test with increasing verbosity: forge test Shortfall.t.sol -vvvv:
[Revert] ERC4626ExceededMaxWithdraw(0xB38Bff66d567C10F54a96F35ee790d36684bdfB6, 10000000000 [1e10], 0)

## Recommendation

Remove this amountLeft -= assetBalance; and change amountLeft with amount in transfers-> asset.safeTransfer(recipient, amountLeft);.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect asset redemption logic in the vault withdrawal routine that causes users to receive less than the amount they request when the vault does not hold enough liquid assets to satisfy the withdrawal. The root cause is a faulty calculation in the withdrawAssets function: when the vault's immediate asset balance is lower than the withdrawal request, the code subtracts that balance from the requested amount (amountLeft -= assetBalance) and then only transfers the remaining shortfall that is redeemed from pending orders. At the same time the vault burns shares corresponding to the full requested amount, so the user's share balance is reduced by the whole withdrawal even though only a fraction of the assets were actually transferred. This bug is triggered whenever a withdrawal request exceeds the vault's on‑chain asset balance, which can happen during periods of high redemption pressure or after large deposits have been allocated to orders. An attacker does not need to craft a special transaction; any user can simply request a withdrawal larger than the vault’s liquid pool and will be under‑paid. The impact is three‑fold: the user receives only the shortfall amount (for example 200 tokens instead of 1200), the burned shares permanently erase the untransferred portion (the user loses the remaining 1000 tokens), and any subsequent withdrawal attempts fail because the share balance no longer matches the available assets, causing the ERC4626ExceededMaxWithdraw revert. From the user’s perspective the UI shows a successful withdrawal but the token balance increases by far less than expected, and further attempts to withdraw the missing funds are rejected, leading to confusion and potential loss of funds. The issue was discovered during a manual audit by Spearbit and reproduced with a dedicated test (Shortfall.t.sol) that logs the discrepancy and the subsequent revert. It can be hard to notice because the transaction does not revert; it merely transfers an incorrect amount, which may be overlooked if the user does not compare the requested and received values. The proper fix is to remove the subtraction of the vault’s balance from the amount left and to transfer the full requested amount (or the actual available amount) while burning shares only for the amount that is truly transferred, ensuring that share accounting matches the assets moved. This correction restores the invariant that the number of burned shares equals the amount of assets withdrawn, preventing under‑payment and preserving user funds.
