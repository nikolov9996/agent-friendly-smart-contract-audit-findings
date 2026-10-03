---
id: 25017
severity: "Crit/High"
---

# The user overpays the USDA amount for downside protection while withdrawing

## Description



## Proof of Concept

## Impact

Users should return usda amount for downside protection and the protocol doesn't cover downside protection.

## Recommendation

Deduct downside protection.

```diff
    function withdraw(
        ITreasury.DepositDetails memory depositDetail,
        IBorrowing.BorrowWithdraw_Params memory params,
        IBorrowing.Interfaces memory interfaces
    ) external returns (IBorrowing.BorrowWithdraw_Result memory) {

        ...

        // Calculate the USDa to burn
        uint256 burnValue = depositDetail.borrowedAmount - discountedCollateral;

        // Burn the USDa from the Borrower
        bool success = interfaces.usda.burnFromUser(msg.sender, burnValue);
        if (!success) revert IBorrowing.Borrow_BurnFailed();

        ...

        //Transfer the remaining USDa to the treasury
        bool transfer = interfaces.usda.transferFrom(
            msg.sender,
            address(interfaces.treasury),
-           (borrowerDebt - depositDetail.borrowedAmount) + discountedCollateral
+           (borrowerDebt - depositDetail.borrowedAmount - downsideProtected) + discountedCollateral
        );
        if (!transfer) revert IBorrowing.Borrow_USDaTransferFailed();
        ...
    }
```
