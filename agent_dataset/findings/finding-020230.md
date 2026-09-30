---
id: 20230
severity: "High"
---

# Settlement can be called when auction period ends

## Description

The end of auction period is included in it across the logic, but settlePoolDebt() treats the last moment as if it is beyond the period.
In settlePoolDebt() SettlerActions.sol#L113 the end of period control do not revert at block.timestamp == kickTime + 72 hours, allowing to run the settlement at the very last moment of the period.
Pool manipulations become possible at this point of time as both quote and collateral removal operations (guarded by _revertIfAuctionClearable) and settlePoolDebt() are available at this point of time.
As an example, HPB depositor can monitor pool state and upon the calculation that their bucket can be used for bad debt settlement, atomically run removeQuoteToken() -> settlePoolDebt() -> addQuoteToken() at block.timestamp == kickTime + 72 hours, retaining yield generating HPB position, while funds of other depositors in nearby buckets are used for bad debt.
While the probability looks to be medium, catching the exact moment is cumbersome but achievable operation, the impact is one depositor profiting off others in a risk-free manner, so placing the overall severity to be medium.
settlePoolDebt() can be run at block.timestamp == kickTime + 72 hours:
external/SettlerActions.sol#L100-L113
```solidity
function settlePoolDebt(
    AuctionsState storage auctions_,
    mapping(uint256 => Bucket) storage buckets_,
    DepositsState storage deposits_,
    LoansState storage loans_,
    ReserveAuctionState storage reserveAuction_,
    PoolState calldata poolState_,
    SettleParams memory params_
) external returns (SettleResult memory result_) {
    uint256 kickTime = auctions_.liquidations[params_.borrower].kickTime;
    if (kickTime == 0) revert NoAuction();
    Borrower memory borrower = loans_.borrowers[params_.borrower];
    if ((block.timestamp - kickTime < 72 hours) && (borrower.collateral != 0)) revert AuctionNotClearable();
```
While AuctionNotCleared() is block.timestamp - kickTime > 72 hours, i.e. clearable auction is [0, 72 hours] period:
helpers/RevertsHelper.sol#L50-L57
```solidity
function _revertIfAuctionClearable(
    AuctionsState storage auctions_,
    LoansState storage loans_
) view {
    address head = auctions_.head;
    uint256 kickTime = auctions_.liquidations[head].kickTime;
    if (kickTime != 0) {
        if (block.timestamp - kickTime > 72 hours) revert AuctionNotCleared();
```
Reserves take also includes the last timestamp to the period, proceeding with take:
external/TakerActions.sol#L282-L291
```solidity
function takeReserves(
    ReserveAuctionState storage reserveAuction_,
    uint256 maxAmount_
) external returns (uint256 amount_, uint256 ajnaRequired_) {
    // revert if no amount to be taken
    if (maxAmount_ == 0) revert InvalidAmount();
    uint256 kicked = reserveAuction_.kicked;
    if (kicked != 0 && block.timestamp - kicked <= 72 hours) {
```

## Proof of Concept

no poc

## Recommendation

Consider having settlePoolDebt() wait for the whole period to pass:
external/SettlerActions.sol#L100-L113
```solidity
function settlePoolDebt(
    ...
) external returns (SettleResult memory result_) {
    ...
    if ((block.timestamp - kickTime <= 72 hours) && (borrower.collateral != 0)) revert AuctionNotClearable();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one time boundary error that allows the settlement function to be executed at the exact moment an auction period ends. The protocol defines an auction as clearable only after more than 72 hours have elapsed since the kick time, using a strict greater‑than check (block.timestamp - kickTime > 72 hours) in the helper that guards quote and collateral removal. However, the settlePoolDebt function checks the opposite condition with a strict less‑than test (block.timestamp - kickTime < 72 hours) before reverting, which means that when block.timestamp equals kickTime + 72 hours the function does not revert and can be called. This mismatch creates a narrow window – the final block of the auction – where both the removal operations guarded by _revertIfAuctionClearable and the settlement logic are simultaneously available. An attacker who monitors the blockchain can, at that precise timestamp, atomically execute a sequence such as removeQuoteToken, settlePoolDebt, and addQuoteToken. By doing so the attacker can use the pool’s quote token balance to cover a bad‑debt position while immediately re‑adding the same amount, thereby retaining any yield‑generating position they held. The funds used to settle the debt are taken from other depositors’ buckets, causing those users to lose value without receiving the expected refund or yield. From a user’s perspective the symptom is a sudden reduction or disappearance of their deposited balance or accrued interest after an auction finishes, contrary to the expectation that their funds remain untouched. The issue was discovered during a manual audit that compared the time checks across the contract’s auction‑related functions and identified the inclusive/exclusive inconsistency. It is hard to notice because it only manifests at a single block height, making it easy to miss in routine testing. The conceptual fix is to align the time comparison in settlePoolDebt with the rest of the protocol, for example by using a less‑than‑or‑equal check (block.timestamp - kickTime <= 72 hours) or by requiring the full auction period to have elapsed before allowing settlement. This would close the window that enables the atomic manipulation and restore the intended accounting guarantees of the protocol.
