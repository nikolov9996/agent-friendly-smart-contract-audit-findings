---
id: 1314
severity: "High"
---

# Wrong shortfall calculation

## Description

Every time an account is settled, if shortfall is created, due to a wrong calculation shortfall will double in size and add the new shortfall.

## Proof of Concept

We can see in the `settleAccount` of `OptimisticLedger` that `self.shortfall` ends up being `self.shortfall+self.shortfall+newShortfall`: [(Code ref)](https://github.com/code-423n4/2021-12-perennial/blob/main/protocol/contracts/collateral/types/OptimisticLedger.sol#L63:#L74)
```solidity
function settleAccount(OptimisticLedger storage self, address account, Fixed18 amount)
internal returns (UFixed18 shortfall) {
    Fixed18 newBalance = Fixed18Lib.from(self.balances[account]).add(amount);

    if (newBalance.sign() == -1) {
        shortfall = self.shortfall.add(newBalance.abs());
        newBalance = Fixed18Lib.ZERO;
    }

    self.balances[account] = newBalance.abs();
    self.shortfall = self.shortfall.add(shortfall);
}
```

Additionally, you can add the following line to the “shortfall reverts if depleted” test in `Collateral.test.js`, line 190:
```solidity
await collateral.connect(productSigner).settleAccount(userB.address, -50)
```

Previously the test product had 50 shortfall. Now we added 50 more, but the test will print that the actual shortfall is 150, and not 100 as it should be.

## Recommendation

Move the setting of `self.shortfall` to inside the if function and change the line to:
```solidity
self.shortfall = shortfall
```

Excellent find 🙏 

Agree with the finding `shortfall = self.shortfall.add(newBalance.abs());` is already shortfal + newBalance.abs() So performing line `73` `self.shortfall = self.shortfall.add(shortfall);` is adding `shortfall` again

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect accounting of the collateral shortfall inside the ledger's settlement routine. When an account's balance becomes negative, the contract calculates a temporary shortfall value as the current accumulated shortfall plus the absolute value of the new negative balance. However, after this calculation the code adds the temporary shortfall to the stored shortfall again, effectively performing self.shortfall = self.shortfall + (self.shortfall + newDeficit). This double‑addition means that each settlement that creates a deficit inflates the recorded shortfall by roughly twice the actual amount, causing the shortfall figure to grow faster than the underlying economic loss. The flaw is triggered whenever the settleAccount function processes a negative balance, which can happen during normal repayment, withdrawal, or liquidation flows. From a user's perspective the protocol appears to report a larger deficit than expected – for example a user who anticipates the shortfall to increase from 50 to 100 will see it jump to 150, leading to unexpected reverts, denied borrowing requests, or premature liquidation events. The impact reaches all participants that rely on the shortfall metric for risk assessment, including lenders, borrowers, and the protocol's governance logic, because the inflated shortfall may cause the system to believe it is under‑collateralized and consequently halt new activity or trigger unnecessary liquidations. The issue was uncovered by the Code4rena audit team during a functional test that checks the shortfall reverts behavior; the test revealed a mismatch between the expected shortfall (100) and the actual value (150), highlighting the double counting. The bug is subtle because the shortfall variable is intended to be cumulative, so adding the newly computed amount appears syntactically correct, masking the logical error. To remediate, the assignment of the shortfall should be moved inside the conditional block and set directly to the newly calculated deficit, i.e., self.shortfall = shortfall, rather than adding the new shortfall to the existing value. Conceptually, the fix ensures that the shortfall reflects the true net deficit without double‑counting, restoring accurate accounting and preserving the protocol's financial invariants.
