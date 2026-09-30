---
id: 4981
severity: "High"
---

# Withdrawing from the vault may lead to a loss if the order balances are less than the total amount withdrawn Submitted by Nyksx

## Description

When the user withdraws, the withdrawAssets function calls the _burnFromOrder()
if the order is not mature yet.
```solidity
else if (block.timestamp < orderInfo.maturity) {
    // withraw ft and xt from order to burn
    uint256 maxWithdraw = orderInfo.xt.balanceOf(order).min(orderInfo.ft.balanceOf(order));
    if (maxWithdraw < amountLeft) {
        amountLeft -= maxWithdraw;
        _burnFromOrder(ITermMaxOrder(order), orderInfo, maxWithdraw);
        //@audit-issue it burns from the order but didnt transfer
        ++i;
    } else {
        _burnFromOrder(ITermMaxOrder(order), orderInfo, amountLeft);
        asset.safeTransfer(recipient, amountLeft);
        amountLeft = 0;
        break;
    }
} else {
    // ignore orders that are in liquidation window
    ++i;
}
```
The function can only burn an amount equal to the minimum balance of the XT or FT token that the order has. If the withdrawal amount exceeds the maximum burnable amount, the function updates the amountLeft, burns the necessary amount from the current order, and then moves on to the next order to fulfill the withdrawal.
The problem is that the function updates the amountLeft but does not transfer the maxWithdraw amount of tokens to the user after burning from the order. When it moves on to the next order, it only transfers amountLeft - maxWithdraw to the user.

Impact Explanation:
If the balance of orders XT or FT is less than the user's withdrawal amount, the user will incur a loss of funds.

## Proof of Concept

```solidity
function testRedeemWhenTheXtBalanceLessThanWithdrawalAmount() public {
    vm.warp(currentTime + 3 days);
    address lper2 = vm.randomAddress();
    uint256 amount2 = 10000e8;
    res.debt.mint(lper2, amount2);
    vm.startPrank(lper2);
    res.debt.approve(address(vault), amount2);
    uint256 shares = vault.deposit(amount2, lper2);
    vm.stopPrank();
    vm.startPrank(curator);
    address order2 = address(vault.createOrder(market2, maxCapacity, 0, orderConfig.curveCuts));
    uint256[] memory indexes = new uint256[](2);
    indexes[0] = 1;
    indexes[1] = 0;
    vault.updateSupplyQueue(indexes);
    res.debt.mint(curator, 10000e8);
    res.debt.approve(address(vault), 10000e8);
    vault.deposit(10000e8, curator);
    vm.stopPrank();
    vm.warp(currentTime + 4 days);
    // Buy some XT so the XT balance will be less than the withdrawal amount
    {
        address taker = vm.randomAddress();
        uint128 tokenAmtIn = 1000e8;
        res.debt.mint(taker, tokenAmtIn);
        vm.startPrank(taker);
        res.debt.approve(address(res.order), tokenAmtIn);
        res.order.swapExactTokenToToken(res.debt, res.xt, taker, tokenAmtIn, 12000e8);
        vm.stopPrank();
    }
    // User withdraws
    vm.startPrank(lper2);
    uint256 userDebtTokenBalaceBefore = res.debt.balanceOf(lper2);
    console.log("users shares before", vault.balanceOf(lper2));
    console.log("user debt token balance before", userDebtTokenBalaceBefore);
    vault.redeem(shares, lper2, lper2);
    uint256 userDebtTokenBalaceAfter = res.debt.balanceOf(lper2);
    console.log("users shares after", vault.balanceOf(lper2));
    console.log("user debt token balance after", userDebtTokenBalaceAfter);
    vm.stopPrank();
}
```
Even if the user burns 1e12 shares, they will receive only 1e11 debt tokens in return:
Logs:
users shares before 1000000000000
user debt token balance before 0
users shares after 0
user debt token balance after 100000000000

## Recommendation

```solidity
if (maxWithdraw < amountLeft) {
    amountLeft -= maxWithdraw;
    _burnFromOrder(ITermMaxOrder(order), orderInfo, maxWithdraw);
    asset.safeTransfer(recipient, maxWithdraw);
    ++i;
} else {
    _burnFromOrder(ITermMaxOrder(order), orderInfo, amountLeft);
    asset.safeTransfer(recipient, amountLeft);
    amountLeft = 0;
    break;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the withdrawal routine of a vault contract that aggregates multiple orders. When a user initiates a withdrawal before an order reaches its maturity, the contract calculates the maximum amount that can be burned from the order as the minimum of the XT token balance and the FT token balance held by that order. If this maximum (maxWithdraw) is smaller than the remaining amount the user wants to withdraw (amountLeft), the code correctly reduces amountLeft by maxWithdraw and calls an internal burn function to destroy the corresponding tokens from the order. However, the implementation fails to transfer the burned maxWithdraw amount to the caller before moving on to the next order in the queue. Consequently, the user only receives the residual amountLeft that is satisfied by later orders, effectively losing the tokens that were burned in the first step. This logic error occurs only in the branch where the order is not yet mature and its token balances are insufficient, making it easy to miss because the transaction does not revert and the UI may simply show that the user's shares were redeemed. From a user’s perspective the symptom is a mismatch between the number of vault shares burned and the amount of underlying debt tokens received – users may see their share balance drop to zero while their token balance increases by far less than expected, sometimes appearing as “funds disappear” or “refund is missing”. The root cause is a missing asset.safeTransfer call after a partial burn, a classic example of an accounting or accounting‑logic bug where the contract’s internal state is updated without reflecting the same change in external balances. The issue was discovered during a manual audit by Spearbit, who observed that the withdrawal path does not honour the full amount that should be returned when order balances are low. The bug is hard to notice because the contract does not emit an explicit error; it merely under‑delivers, which can be attributed to market conditions or rounding errors. The impact is high‑risk: any user withdrawing an amount larger than the smallest token balance of an immature order can lose a portion of their funds, effectively reducing the total assets they can reclaim from the vault. The affected parties are liquidity providers and any participants who rely on the vault’s redemption mechanism. To remediate the problem the withdrawal logic must be amended to transfer the maxWithdraw amount to the recipient immediately after burning it, ensuring that the external token balance matches the internal accounting. This aligns the contract’s behavior with the expected business logic that a withdrawal should return the full value of the burned assets, preventing silent loss of funds.
