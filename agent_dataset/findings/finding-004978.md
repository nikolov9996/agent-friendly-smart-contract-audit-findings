---
id: 4978
severity: "High"
---

# The totalFt and accretingPrincipal are updated incorrectly in withdrawAssets Submitted by Nyksx, also found by BengalCatBalu, Joshuajee, mohitisimmortal, 0xgh0st and retsoko

## Description

When the user withdraws from the vault, the vault will call the OrderManager.withdrawAssets() function. If the balance exceeds the withdrawal amount, the function transfers the funds directly and updates the parameters. If not, the function attempts to redeem the market or burn tokens from the order to acquire the funds, sends the funds and updates the parameters.
The issue arises when the contract balance is suﬃcient for withdrawal, as it updates the _totalFt and _accretingPrincipal twice. First, it updates after the tokens are sent to the recipient:
```solidity
if (assetBalance >= amount) {
    asset.safeTransfer(recipient, amount);
    //@audit 1st time
    _totalFt -= amount;
    _accretingPrincipal -= amount;
}
```
Secondly, it updates the same parameters at the end of the function:
```solidity
if (amountLeft > 0) {
    uint256 maxWithdraw = amount - amountLeft;
    revert InsufficientFunds(maxWithdraw, amount);
}
}
_totalFt -= amount; //@audit second time
_accretingPrincipal -= amount;
```

Impact Explanation:
After every withdrawal, users share will be worth less due to the wrong totalAssets value.

## Proof of Concept

• Vault.t.sol:
```solidity
function testwithdrawAssets() public {
    vm.warp(currentTime + 2 days);
    buyXt(48.219178e8, 1000e8);
    vm.warp(currentTime + 3 days);
    address lper2 = vm.randomAddress();
    uint256 amount2 = 10000e8;
    res.debt.mint(lper2, amount2);
    vm.startPrank(lper2);
    res.debt.approve(address(vault), amount2);
    vault.deposit(amount2, lper2);
    vm.stopPrank();
    address borrower = vm.randomAddress();
    vm.startPrank(borrower);
    LoanUtils.fastMintGt(res, borrower, 1000e8, 1e18);
    vm.stopPrank();
    vm.warp(currentTime + 92 days);
    uint256 propotion = (res.ft.balanceOf(address(res.order)) * Constants.DECIMAL_BASE_SQ)
        / (res.ft.totalSupply() - res.ft.balanceOf(address(res.market)));
    uint256 tokenOut = (res.debt.balanceOf(address(res.market)) * propotion)
        / Constants.DECIMAL_BASE_SQ;
    uint256 badDebt = res.ft.balanceOf(address(res.order)) - tokenOut;
    uint256 delivered = (propotion * 1e18) / Constants.DECIMAL_BASE_SQ;
    vm.startPrank(lper2);
    vault.redeem(1000e8, lper2, lper2);
    vm.stopPrank();
    assertEq(vault.badDebtMapping(address(res.collateral)), badDebt);
    assertEq(res.collateral.balanceOf(address(vault)), delivered);
    uint256 totalFtBefore = vault.totalFt();
    console.log("Before TotalFT", totalFtBefore);
    console.log("Before Total Assets", vault.totalAssets());
    vm.startPrank(lper2);
    uint256 withdrawAmount = 1e8;
    vault.withdraw(withdrawAmount, lper2, lper2);
    console.log("Withdraw Amount", withdrawAmount);
    uint256 totalFtAfter = vault.totalFt();
    console.log("After TotalFT", totalFtAfter);
    console.log("After Total Assets", vault.totalAssets());
    console.log("Difference", totalFtBefore - totalFtAfter);
    vm.stopPrank();
}
```
Logs:
Before TotalFT 1904578075654
Before Total Assets 1904578075653
Withdraw Amount 100000000
After TotalFT 1904378075654
After Total Assets 1904378075653
Difference 200000000

## Recommendation

```solidity
function withdrawAssets(IERC20 asset, address recipient, uint256 amount) external override onlyProxy {
    _accruedInterest();
    uint256 amountLeft = amount;
    uint256 assetBalance = asset.balanceOf(address(this));
    if (assetBalance >= amount) {
        asset.safeTransfer(recipient, amount);
        //@audit 1st time
        _totalFt -= amount;
        _accretingPrincipal -= amount;
    } else {
        amountLeft -= assetBalance;
        uint256 length = _withdrawQueue.length;
        // withdraw from orders
        uint256 i;
        while (length > 0 && i < length) {
            // ... withdrawal logic ...
        }
        if (amountLeft > 0) {
            uint256 maxWithdraw = amount - amountLeft;
            revert InsufficientFunds(maxWithdraw, amount);
        }
        _totalFt -= amount;
        _accretingPrincipal -= amount;
    }
    // -_totalFt -= amount;
    // -_accretingPrincipal -= amount;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains an accounting flaw in the withdrawAssets function of the vault. When a user requests a withdrawal and the vault's on‑chain balance is sufficient, the function transfers the requested amount and then subtracts the withdrawn amount from two internal accounting variables, _totalFt and _accretingPrincipal. However, after the conditional block the same subtraction is performed again unconditionally at the end of the function. As a result the internal total asset counters are reduced twice for a single successful transfer. The bug originates from duplicated state updates rather than a single, mutually exclusive path. An attacker does not need to craft a special payload; any normal withdrawal that meets the sufficient‑balance branch triggers the double decrement. The immediate impact is that the reported total assets and the per‑share value become lower than the actual token balances held by the vault. Users see their share price shrink, and subsequent deposits or withdrawals are calculated against an understated pool, effectively eroding the value of all participants' holdings. The condition occurs whenever the vault balance covers the withdrawal amount, which is the most common case for regular users. The issue was discovered during a formal audit and reproduced with a unit test that logged totalFt before and after a withdrawal, showing a discrepancy equal to the withdrawn amount. Because the external transfer succeeds and no revert is emitted, the problem is subtle and may go unnoticed unless internal accounting metrics are compared against on‑chain balances. To remediate, the contract should ensure that the subtraction of _totalFt and _accretingPrincipal happens exactly once per withdrawal, either by moving the updates outside the conditional or by guarding the final decrement with an else clause, and by removing the duplicated statements. This correction restores the invariant that total assets reported by the vault match the actual token holdings, preserving share value and preventing inadvertent loss of value for all users.
