---
id: 21532
severity: "High"
---

# Risk of overpayment due to race condition between `repay` and `liquidateWithReplacement` transactions

## Description

* **Likelihood** : Medium - Users and liquidation bots are likely to call their respective functions around the same time.
* **Impact** : High - Users end up repaying more than double their future value.

## Proof of Concept

The `LiquidateWithReplacement` mechanism in the Size protocol allows a permissioned role (`KEEPER_ROLE`) to perform the liquidation of a debt position by replacing an unhealthy borrower with a healthier one from the order book. Here’s how it works:

1. The debt position of the unhealthy borrower is liquidated, and the `futureValue` is paid to the Size contract by the liquidator,while the liquidator gets an equivalent amount plus reward in terms of collateral tokens from the unhealthy borrower.
2. The borrower of this `debtPosition` is updated to the new healthier borrower.
3. The debt position retains its same `futureValue` and `ID`.
4. A portion of the repaid funds is used to fund a new borrower.

```solidity
function executeLiquidateWithReplacement(State storage state, LiquidateWithReplacementParams calldata params)
    external
    returns (uint256 issuanceValue, uint256 liquidatorProfitCollateralToken, uint256 liquidatorProfitBorrowToken)
{
  // some code ...
  // >>    liquidatorProfitCollateralToken = state.executeLiquidate(LiquidateParams({debtPositionId: params.debtPositionId, minimumCollateralProfit: params.minimumCollateralProfit}));

    uint256 ratePerTenor = borrowOffer.getRatePerTenor(
        VariablePoolBorrowRateParams({
            variablePoolBorrowRate: state.oracle.variablePoolBorrowRate,
            variablePoolBorrowRateUpdatedAt: state.oracle.variablePoolBorrowRateUpdatedAt,
            variablePoolBorrowRateStaleRateInterval: state.oracle.variablePoolBorrowRateStaleRateInterval
        }),
        tenor
    );
    issuanceValue = Math.mulDivDown(debtPositionCopy.futureValue, PERCENT, PERCENT + ratePerTenor);
    liquidatorProfitBorrowToken = debtPositionCopy.futureValue - issuanceValue;

  // >>      debtPosition.borrower = params.borrower;
  // >>      debtPosition.futureValue = debtPositionCopy.futureValue;
    debtPosition.liquidityIndexAtRepayment = 0;

    emit Events.UpdateDebtPosition(params.debtPositionId, debtPosition.borrower, debtPosition.futureValue, debtPosition.liquidityIndexAtRepayment);
    // @note : in this case the borrower doesn't pay swapFees
    state.data.debtToken.mint(params.borrower, debtPosition.futureValue);
  // >>   state.data.borrowAToken.transferFrom(address(this), params.borrower, issuanceValue);
    state.data.borrowAToken.transferFrom(address(this), state.feeConfig.feeRecipient, liquidatorProfitBorrowToken);
}
```

By maintaining the same debt position ID and future value, lenders (all credit holders of this debt position) can still expect repayment on the original due date.

On the other hand, a user can always `repay` a debt position. To repay, the user specifies the `ID` of the debt position and calls the `repay` function, which repays the loan of the specified debt position.
    
```solidity
function executeRepay(State storage state, RepayParams calldata params) external {
    DebtPosition storage debtPosition = state.getDebtPosition(params.debtPositionId);

    state.data.borrowAToken.transferFrom(msg.sender, address(this), debtPosition.futureValue);
    debtPosition.liquidityIndexAtRepayment = state.data.borrowAToken.liquidityIndex();
    state.repayDebt(params.debtPositionId, debtPosition.futureValue);

    emit Events.Repay(params.debtPositionId);
}
```

The issue arises when a borrower sends a transaction to `repay` their debt position when it becomes liquidatable, but a `liquidateWithReplacement` transaction is executed just before the user’s transaction. This way, the user will be liquidated, and their collateral will be used to repay debt. Since `liquidateWithReplacement` only changes the borrower of a `debtPosition`, the user ends up paying the debt of another borrower immediately, resulting in the user repaying more than double their future value (more than 2x because of liquidation rewards).

This doesn’t require a malicious keeper (who calls `liquidateWithReplacement`) as it’s trusted, it can happen unintentionally, and there is a pretty good chance for this to occur; as users and the liquidator (keeper bot in this case) will probably call their respective functions around the same time.

When a user notices that their position is liquidatable (probably through a UI notification), there is a high chance they will repay their debt to avoid liquidation, and the same goes for the liquidation bot. Thus, there is a good chance that the `liquidateWithReplacement` transaction will be executed before the user’s repayment transaction. The impact is high here, as the user ends up paying 2x their debt.

In case `liquidateWithReplacement` becomes permissionless and anyone can call it, this will be critically exploitable. An exploit scenario would be:

1. The collateral token price drops, making Bob’s position liquidatable.
2. Bob gets notified and sends a transaction to repay his debt position with `ID=0`.
3. Alice sees Bob’s transaction in the mempool and front-runs him to liquidate the debt position with `ID=0`, setting herself as the borrower (it can set any curve borrow offer). An equivalent amount to the `futureValue` in terms of collateral tokens is sent from Bob’s account to Alice, and Alice receives another cash of `borrowAToken` since she’s the borrower.
4. Bob’s transaction gets executed after that, and Bob ends up paying Alice’s debt. Bob suffers loss.

## Recommendation

To prevent unintended debt repayment due to borrower changes, users should specify both the borrower address and the debt position ID when repaying. This ensures users have control over who they are repaying for, avoiding scenarios where they might repay another borrower’s debt due to a recent `liquidateWithReplacement` transaction.

Make this changes in [repay lib](https://github.com/code-423n4/2024-06-size/blob/8850e25fb088898e9cf86f9be1c401ad155bea86/src/libraries/actions/Repay.sol):
    
```solidity
struct RepayParams {
    uint256 debtPositionId;
    address borrower;
}

function validateRepay(State storage state, RepayParams calldata params) external view {
    // validate debtPositionId
    if (state.getLoanStatus(params.debtPositionId) == LoanStatus.REPAID) {
        revert Errors.LOAN_ALREADY_REPAID(params.debtPositionId);
    }
    if (state.getDebtPosition(params.debtPositionId).borrower != params.borrower) revert("invalid borrower");

    // validate msg.sender
    // N/A
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a race condition that occurs when a borrower tries to repay a debt position at the same time a keeper bot executes the liquidateWithReplacement function. The liquidateWithReplacement operation replaces the unhealthy borrower with a new one but deliberately keeps the same debt position identifier and the same future value. Because the repay function only checks the debt position identifier and does not verify that the caller is still the borrower of that position, a repayment transaction that is mined after the liquidation will credit the caller’s funds against the new borrower’s debt. As a result the original borrower unintentionally pays the debt of the replacement borrower, effectively repaying more than twice the amount they owed because the liquidation also distributes a reward to the liquidator. This can be triggered whenever two transactions – a repayment and a liquidation – are submitted in close temporal proximity, which is common when users receive UI alerts that their position is liquidatable and attempt to repay immediately while a keeper bot is also monitoring the same condition. If an attacker observes the pending repayment in the mempool, they can front‑run the transaction with a liquidation, causing the borrower to lose funds. The impact is that the borrower’s balance is reduced by an amount greater than the original debt, often appearing as a missing or zeroed balance after the transaction, while the liquidator gains the reward. The issue affects any user who holds a debt position, the protocol’s accounting logic, and lenders who expect repayment on the original schedule. It was discovered during a security audit that examined the interaction between the repay library and the liquidation library and identified that the borrower address is not part of the repayment validation. The bug is subtle because the protocol emits an event updating the borrower, but the UI may not highlight the change before the repayment is processed, leading users to believe they are repaying their own debt. Conceptually, the fix is to require both the debt position ID and the borrower address in the repayment call and to validate that the supplied borrower matches the current owner of the position, thereby preventing a repayment from being applied to a different borrower after a replacement liquidation. This change restores the intended accounting invariant that a repayment always reduces the debt of the borrower who initiated it and eliminates the over‑payment scenario.
