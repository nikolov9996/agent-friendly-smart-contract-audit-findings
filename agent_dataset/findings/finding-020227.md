---
id: 20227
severity: "High"
---

# Pool's kickWithDeposit misses liquidation debt

## Description

_revertIfAuctionDebtLocked() is missed in kickWithDeposit() function, that can actually remove deposit from anywhere, including HPB that are frozen by liquidation debt accumulator.
The inability to remove quote token deposit that is placed high enough to be covered by liquidation debt accumulator is a part of system design (see 7.5 Liquidation Debt of Ajna protocol white paper).
The corresponding check is performed by _revertIfAuctionDebtLocked() in moveQuoteToken() and removeQuoteToken(), but is missed in kickWithDeposit() that allows for quote funds retrieval from HPB as well.
HPB depositors can use kickWithDeposit() -> withdrawBonds() for quote funds removal, effectively avoiding liquidation debt controls, which can lead to deposit shortage for the matters of eventual bad debt coverage. I.e. in some situations when depositor knows that his funds are about to be used to cover bad debt it might be reasonable for them to use kickWithDeposit() even knowing that there most probably will be a kicker penalty imposed.
This not only can create a number of bad faith auctions, but can move a burden of debt write offs to lower bucket depositors, who are unaware of such possibility and do not actively monitor pool state. This will allow HPB depositors to obtain stable yield, but off load a part of the corresponding risks, profiting off the lower buckets depositors (who, in general, pocketed a somewhat lower yield, but receive more risk this way).
As there is no low-probability prerequisites and the impact is a violation of system design allowing one group of users to profit off another, setting the severity to be high.
kickWithDeposit() can effectively remove quote tokens from any bucket to cover kick bond, but is not controlled for liquidation debt buffer:
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
    // amount to remove from deposit covers entire bond amount
    if (vars.amountToDebitFromDeposit > kickResult_.amountToCoverBond) {
        // cap amount to remove from deposit at amount to cover bond
        vars.amountToDebitFromDeposit = kickResult_.amountToCoverBond;
        // recalculate the LUP with the amount to cover bond
        kickResult_.lup = Deposits.getLup(deposits_, poolState_.debt + vars.amountToDebitFromDeposit);
        // entire bond is covered from deposit, no additional amount to be send by lender
        kickResult_.amountToCoverBond = 0;
    } else {
        // lender should send additional amount to cover bond
        kickResult_.amountToCoverBond -= vars.amountToDebitFromDeposit;
    }
    // revert if the bucket price used to kick and remove is below new LUP
    if (vars.bucketPrice < kickResult_.lup) revert PriceBelowLUP();
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
_revertIfAuctionDebtLocked() is guarding direct quote funds removal via moveQuoteToken():
ol.sol#L176-L185
```solidity
function moveQuoteToken(
    uint256 maxAmount_,
    uint256 fromIndex_,
    uint256 toIndex_,
    uint256 expiry_
) external override nonReentrant returns (uint256 fromBucketLP_, uint256 toBucketLP_, uint256 movedAmount_) {
    _revertAfterExpiry(expiry_);
    PoolState memory poolState = _accruePoolInterest();
    _revertIfAuctionDebtLocked(deposits, poolState.t0DebtInAuction, fromIndex_, poolState.inflator);
```
And removeQuoteToken():
ol.sol#L210-L218
```solidity
function removeQuoteToken(
    uint256 maxAmount_,
    uint256 index_
) external override nonReentrant returns (uint256 removedAmount_, uint256 redeemedLP_) {
    _revertIfAuctionClearable(auctions, loans);
    PoolState memory poolState = _accruePoolInterest();
    _revertIfAuctionDebtLocked(deposits, poolState.t0DebtInAuction, index_, poolState.inflator);
```

## Proof of Concept

no poc

## Recommendation

Consider adding the check:
ol.sol#L321-L336
```solidity
function kickWithDeposit(
    uint256 index_,
    uint256 npLimitIndex_
) external override nonReentrant {
    PoolState memory poolState = _accruePoolInterest();
    _revertIfAuctionDebtLocked(deposits, poolState.t0DebtInAuction, index_, poolState.inflator);
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

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing liquidation‑debt lock check in the pool function that processes a kick with a deposit. The protocol is designed so that quote‑token deposits that are earmarked to cover potential bad debt – the liquidation‑debt buffer – cannot be withdrawn directly. This protection is enforced by the internal helper _revertIfAuctionDebtLocked, which is called by the functions moveQuoteToken and removeQuoteToken before any quote‑token removal. However, the kickWithDeposit entry point, which allows a depositor to trigger a liquidation auction and simultaneously withdraw quote tokens to cover the kicker bond, does not invoke this guard. As a result, a high‑price bucket (HPB) depositor can call kickWithDeposit, invoke withdrawBonds, and extract quote tokens that should remain locked for debt coverage. The root cause is an oversight in the function’s access‑control flow: the developer added the debt‑lock check to other removal paths but omitted it from the kick path.

Exploitation is straightforward. An attacker who holds a deposit in a bucket whose price is high enough to be covered by the liquidation‑debt accumulator calls kickWithDeposit with the index of that bucket. The contract calculates the amount needed to cover the kicker bond, caps the debit from the deposit, and then removes the quoted amount without any verification that the bucket’s quote balance is part of the locked debt buffer. Because the check is absent, the contract permits the full withdrawal even when the bucket’s quote tokens are supposed to be frozen. The attacker may still incur the normal kicker penalty, but they can escape the debt‑locking mechanism entirely.

The impact is a systematic erosion of the pool’s bad‑debt coverage. When HPB depositors extract locked quote tokens, the liquidation‑debt buffer shrinks, leaving lower‑price buckets – which are typically held by smaller or less‑active participants – exposed to uncovered bad debt. Those lower‑bucket depositors may see their expected yields reduced and, in extreme cases, may experience unexpected losses because the protocol must write off debt against their remaining deposits. From a user‑facing perspective, a depositor who expects a refund or a stable yield may instead see their balance drop to zero or receive a zero‑amount refund after an auction, without any obvious on‑chain error. The bug violates the accounting assumption that quote tokens reserved for liquidation debt remain immutable until the debt is resolved.

The condition under which the flaw manifests is any call to kickWithDeposit on a bucket that contains quote tokens locked by the liquidation‑debt accumulator. It does not require a rare state; the only prerequisite is that the caller has a deposit in such a bucket and initiates a kick. The issue was discovered during a manual audit of the Ajna protocol code, where the auditor noticed that the debt‑lock guard was present in moveQuoteToken and removeQuoteToken but absent in kickWithDeposit. Because the function still appears to work correctly – it successfully removes quote tokens and updates the pool state – the problem can be subtle and may only be observed through anomalous accounting results or unexpected reductions in the debt buffer.

Fixing the issue involves adding the same _revertIfAuctionDebtLocked guard at the beginning of kickWithDeposit, using the same parameters (deposits, current auction debt, bucket index, inflator) as the other removal functions. This ensures that any attempt to withdraw quote tokens from a bucket that is part of the liquidation‑debt buffer will be rejected, restoring the intended protection and preserving the integrity of the pool’s bad‑debt coverage model.
