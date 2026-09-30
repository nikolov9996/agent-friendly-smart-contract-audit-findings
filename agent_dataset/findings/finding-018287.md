---
id: 18287
severity: "High"
---

# Uneven deduction of performance fee causes some KangarooVault users to lose part of their token value

## Description

In `KangarooVault._resetTrade()`, a `performanceFee` is charged upon closing of all positions, on the `premiumCollected`. This is inconsistent with `getTokenPrice()` as `premiumCollected` is factored in the token price computation, while the `performanceFee` is not. This leads to an uneven distribution of the `performanceFee` for the `KangarooVault` users.

## Proof of Concept

Add the following imports and test case to `test/KangarooVault.t.sol`
    
```solidity
import {IVaultToken} from "../src/interfaces/IVaultToken.sol";

function testKangarooPerformanceFee() public {
    uint256 amt = 231e18;
    IVaultToken vaultToken = IVaultToken(kangaroo.VAULT_TOKEN());

    // deposit equal value for both user_2 and user 3 into KangarooVault
    uint256 depositAmt = 10e18;
    susd.mint(user_2, depositAmt);
    vm.startPrank(user_2);
    susd.approve(address(kangaroo), depositAmt);
    kangaroo.initiateDeposit(user_2, depositAmt);
    assertEq((vaultToken.balanceOf(user_2) * kangaroo.getTokenPrice())/1e18, depositAmt);
    vm.stopPrank();

    susd.mint(user_3, depositAmt);
    vm.startPrank(user_3);
    susd.approve(address(kangaroo), depositAmt);
    kangaroo.initiateDeposit(user_3, depositAmt);
    assertEq((vaultToken.balanceOf(user_2) * kangaroo.getTokenPrice())/1e18, depositAmt);
    vm.stopPrank();

    skip(14500);
    kangaroo.processDepositQueue(2);

    // Open position at KangarooVault and execute the orders
    kangaroo.openPosition(amt, 0);
    skip(100);
    kangaroo.executePerpOrders(emptyData);
    kangaroo.clearPendingOpenOrders(0);

    // Simulate price drop to trigger profit from premium collection
    setAssetPrice(initialPrice - 100e18);

    // initiate withdrawal for both user_2 and user_3
    vm.prank(user_2);
    kangaroo.initiateWithdrawal(user_2, depositAmt);

    vm.prank(user_3);
    kangaroo.initiateWithdrawal(user_3, depositAmt);

    skip(14500);

    // close all position with gain from premium collection
    kangaroo.closePosition(amt, 1000000e18);
    skip(100);
    kangaroo.executePerpOrders(emptyData);

    // user_2 frontrun clearPendingCloseOrders() to withdraw at higher token price
    kangaroo.processWithdrawalQueue(1);
    assertEq(vaultToken.balanceOf(user_2), 0);
    assertEq(susd.balanceOf(user_2), 9693821343146274141);

    // This will trigger resetTrade and deduct performance Fee
    kangaroo.clearPendingCloseOrders(0);

    // user_3's withdrawal was processed but at a lower token price
    kangaroo.processWithdrawalQueue(1);
    assertEq(vaultToken.balanceOf(user_3), 0);
    assertEq(susd.balanceOf(user_3), 9655768088211372841);

    // This shows that user_3 was shortchanged and lost part of token value, 
    // despite starting with equal token balance
    assertGt(susd.balanceOf(user_2), susd.balanceOf(user_3));
}
```

## Recommendation

Consider changing the following in `KangarooVault.sol#L359`
    
```solidity
totalValue -= (usedFunds + markPrice.mulWadDown(positionData.shortAmount));
```

to
    
```solidity
totalValue -= (usedFunds + markPrice.mulWadDown(positionData.shortAmount) + positionData.premiumCollected.mulWadDown(performanceFee));
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting inconsistency in the KangarooVault contract. When a position is closed the contract records a premiumCollected amount and later charges a performanceFee on that premium. The token price returned by getTokenPrice incorporates the premiumCollected but the performanceFee is subtracted only later in the internal _resetTrade routine. Because the fee is not reflected in the token price calculation, the fee is effectively taken from the pool after the token price has been fixed for pending withdrawals. Users who initiate a withdrawal before the fee deduction receive a higher token price and therefore a larger payout, while users whose withdrawal is processed after the fee deduction receive a lower token price and lose part of the value that was originally accounted for. The bug manifests when a profitable trade is closed, the performance fee is applied, and withdrawals are processed in separate batches. An attacker can front‑run the withdrawal queue, clearing pending close orders for a user with a higher token price before the fee is deducted, and then let other users withdraw later at the reduced price, resulting in an uneven distribution of the fee. The impact is that some participants receive less sUSD than expected, effectively losing part of their deposited value, which violates the protocol’s accounting assumptions that all users share fees proportionally. The issue was discovered during a Code4rena audit by constructing a test that deposits equal amounts for two users, opens a profitable position, and then processes withdrawals in different orders, revealing a discrepancy in the final balances. The problem is subtle because the token price appears correct for early withdrawals, so the loss is only visible for later withdrawals, making it hard to notice without detailed balance tracing. To fix the issue the fee should be deducted from the total value before the token price is computed, ensuring that the performance fee is accounted for in the price that all withdrawals use. In other words, the premiumCollected amount must be reduced by the performanceFee when adjusting totalValue, so that the fee is shared evenly among all vault participants.
