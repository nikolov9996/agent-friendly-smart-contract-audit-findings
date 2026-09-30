---
id: 20228
severity: "High"
---

# kickWithDeposit removes the deposit without

## Description

In order to cover kick bond KickerActions kickWithDeposit() removes the deposit from the pool, but misses the new_LUP >= HTP check, allowing for the invariant breaking state.
that ensures that active loans aren't eligible for liquidation (Ajna white paper 4.1 Deposit).
kickWithDeposit() can effectively remove deposits, either partially or fully, but performs no such check, potentially leaving the pool in the LUP < HTP state.
A range of outcomes becomes possible after that, for example all other deposit operations can be frozen as long as they will not move LUP in the opposite direction, as their HTP checks will revert.
There is no low-probability prerequisites and the impact is a violation of the core system invariant, so setting the severity to be high.
kickWithDeposit() can effectively remove quote tokens from any bucket to cover kick bond:
ol.sol#L321-L336
```solidity
function kickWithDeposit(
    uint256 index_,
    uint256 npLimitIndex_
) external override nonReentrant {
    PoolState memory poolState = _accruePoolInterest();
    // kick auctions
    KickResult memory result = KickerActions.kickWithDeposit(
        auctions,
        deposits,
        buckets,
        loans,
        poolState,
        index_,
        npLimitIndex_
    );
```
external/KickerActions.sol#L149-L243
```solidity
function kickWithDeposit(
    ...
) external returns (
    KickResult memory kickResult_
) {
    ...
    // kick top borrower
    kickResult_ = _kick(
        ...
    );
    ...
    // remove amount from deposits
    if (vars.amountToDebitFromDeposit == vars.bucketDeposit && vars.bucketCollateral == 0) {
        // In this case we are redeeming the entire bucket exactly, and need to ensure bucket LP are set to 0
        vars.redeemedLP = vars.bucketLP;
        Deposits.unscaledRemove(deposits_, index_, vars.bucketUnscaledDeposit);
        vars.bucketUnscaledDeposit = 0;
    } else {
        ...
        Deposits.unscaledRemove(deposits_, index_, unscaledAmountToRemove);
        vars.bucketUnscaledDeposit -= unscaledAmountToRemove;
    }
```
But there is no HTP check:
external/KickerActions.sol#L242-L273
```solidity
vars.bucketUnscaledDeposit -= unscaledAmountToRemove;
}
vars.redeemedLP = Maths.min(vars.lenderLP, vars.redeemedLP);
// revert if LP redeemed amount to kick auction is 0
if (vars.redeemedLP == 0) revert InsufficientLP();
uint256 bucketRemainingLP = vars.bucketLP - vars.redeemedLP;
if (vars.bucketCollateral == 0 && vars.bucketUnscaledDeposit == 0 && bucketRemainingLP != 0) {
    bucket.lps = 0;
    bucket.bankruptcyTime = block.timestamp;
    emit BucketBankruptcy(
    ..
    );
} else {
    // update lender and bucket LP balances
    lender.lps -= vars.redeemedLP;
    bucket.lps -= vars.redeemedLP;
}
emit RemoveQuoteToken(
    ...
);
```

## Proof of Concept

no poc

## Recommendation

to other functions, for example removeQuoteToken():
external/LenderActions.sol#L413-L424
```solidity
lup_ = Deposits.getLup(deposits_, poolState_.debt);
uint256 htp = Maths.wmul(params_.thresholdPrice, poolState_.inflator);
if (
    // check loan book's htp doesn't exceed new lup
    htp > lup_
    ||
    // ensure that pool debt < deposits after removal
    // this can happen if lup and htp are less than min bucket price and htp > lup (since LUP is capped at min bucket price)
    (poolState_.debt != 0 && poolState_.debt > Deposits.treeSum(deposits_))
) revert LUPBelowHTP();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the kickWithDeposit function of the KickerActions contract, which is used to seize a borrower’s position and cover the kick bond by removing quote‑token deposits from a specific bucket. After the borrower is kicked, the function deducts the appropriate amount from the pool’s deposit accounting, but it fails to perform the critical invariant check that the new Lowest Unleveraged Price (LUP) must remain greater than or equal to the Highest Threshold Price (HTP). This missing check allows the pool to enter a state where LUP < HTP, violating the core accounting rule that active loans must never be eligible for liquidation. The bug can be exploited by an attacker who triggers kickWithDeposit on a bucket that can be fully redeemed (or partially redeemed in a way that empties the bucket’s unscaled deposit) while the bucket has no collateral. By doing so, the attacker forces the pool’s LUP to drop below the HTP without any safeguard, causing subsequent deposit‑related operations – such as adding new liquidity, withdrawing, or performing liquidation checks – to revert because they internally enforce the LUP ≥ HTP condition. The impact is a frozen or partially unusable pool: users may see that their attempts to deposit or withdraw quote tokens are rejected, that the pool emits “LUPBelowHTP” style reverts, or that the bucket’s LP balance becomes zero while the pool still reports outstanding debt. This situation can persist until the protocol is manually corrected, potentially locking user funds and breaking the economic guarantees of the system. The condition occurs whenever kickWithDeposit is called and the removal of deposits empties a bucket without collateral, a scenario that is not rare in normal operation. All participants who hold deposits or loans in the affected pool – lenders, borrowers, and the protocol itself – are impacted because the invariant breach undermines the safety of the entire market. The issue was discovered during a manual audit by the researcher Sherlock, who noticed that other functions (for example removeQuoteToken) contain an explicit LUP‑HTP check that is absent here. The bug is subtle because the function otherwise follows the same pattern as the safe removal functions, and the invariant violation only becomes apparent when subsequent operations hit the hidden check, making it easy to miss during routine testing. The recommended remediation is to introduce the same LUP‑HTP validation after the deposit removal step in kickWithDeposit, ensuring that the new LUP is computed and compared against the HTP before any state changes are committed. Additionally, the function should verify that the pool’s total debt remains less than the total deposits after the removal, mirroring the safeguards present in other withdrawal paths. By enforcing these checks, the protocol can maintain its invariant, prevent pool freeze, and protect user funds from disappearing due to an accounting inconsistency.
