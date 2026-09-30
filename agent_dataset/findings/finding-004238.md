---
id: 4238
severity: "High"
---

# [BCCR] Many TCR increasing operations will be blocked when TCR is between 125 and 135

## Description

It looks like after BCCR introduction some healthy TCR increasing openings and adjustments are now blocked.
If oldTCR < newTCR, but ICR <= BCCR, the operation can be denied if TCR < BCCR:
• BorrowerOperations.sol#L398-L413
```solidity
if (isRecoveryMode) {
    _requireICRisAboveCCR(vars.ICR);
} else {
    _requireICRisAboveMCR(vars.ICR);
    uint newTCR = _getNewTCRFromCdpChange(vars.netColl, true, vars.debt, true, vars.price); // bools: coll increase, debt increase

    // See line below
    if (vars.ICR <= BUFFERED_CCR) {
        // Any open CDP is a debt increase so this check is safe
        // If you're dragging TCR toward buffer or RM, we add an extra check for TCR
        // Which forces you to raise TCR to 135+
        _requireNewTCRisAboveBufferedCCR(newTCR);
    } else {
        _requireNewTCRisAboveCCR(newTCR);
    }
}
```
Similarly, when it's ICR increasing collateral withdrawal coupled with debt repayment, or debt increasing coupled with collateral posting, i.e. when one adjusts, making position less risky in the process, it will be blocked when newTCR < BCCR:
• BorrowerOperations.sol#L634-L660
```solidity
if (_isRecoveryMode) {
    // ...
} else {
    // if Normal Mode
    _requireICRisAboveMCR(_vars.newICR);
    _vars.newTCR = _getNewTCRFromCdpChange(
        // ...
    );
    // See line below
    if ((_isDebtIncrease || _collWithdrawal > 0) && _vars.newICR <= BUFFERED_CCR) {
        // Adding debt or reducing coll has negative impact on TCR, do a stricter check
        // If you're dragging TCR toward buffer or RM, we add an extra check for TCR
        // Which forces you to raise TCR to 135+
        _requireNewTCRisAboveBufferedCCR(_vars.newTCR);
    } else {
        // Other cases have a laxer check
        _requireNewTCRisAboveCCR(_vars.newTCR);
    }
}
```
Note, error message in these cases will incorrectly say about TCR decreasing:
• BorrowerOperations.sol#L670-L675
```solidity
function _requireNewTCRisAboveBufferedCCR(uint _newTCR) internal pure {
    require(
        _newTCR >= BUFFERED_CCR,
        "BorrowerOps: A TCR decreasing operation that would result in TCR < BUFFERED_CCR is not permitted"
    );
}
```
Previous to BCCR introduction this was true as both checks happen in non-RM state and if now it's RM the TCR has to be decreased indeed. But once logic becomes 2-tiered it not the case.
It looks like both conditions should involve && newTCR < oldTCR, as if it's not then nothing bad is happening, the system health increases, just not by that much that it's desired, but it might be impossible to achieve for small CDPs in big TVL conditions, which isn't a good reason to block those as system health would have strictly improved.
Impact: many CPD opening and, mostly importantly, CDP adjustment operations that makes the system healthier by increasing TCR will be denied. This is an issue both from UX perspective and protocol stability as the cumulative impact here is that such operations, mostly coming from small CDPs (which will constitute the bigger percentage of all accounts over time along with TVL growth) will not be carried out, so there will be a downward pressure on TCR compared to the situation before the change. I.e. some operations will be carried over with bigger funds brought in, but this will be less and less possible for an average CDP owner over time, and the bigger share of operations will be just cancelled. This will result in lower TCR.
Per high likelihood and medium impact setting the severity to be high.

## Proof of Concept

no poc

## Recommendation

Consider requiring the BCCR only when there was a decrease of TCR as a result of the operation, which was the initial rationale for buffer introduction, for example:
• BorrowerOperations.sol#L375-L413
```solidity
- bool isRecoveryMode = _checkRecoveryModeForTCR(_getTCR(vars.price));
+ uint oldTCR = _getTCR(vars.price);
+ bool isRecoveryMode = _checkRecoveryModeForTCR(oldTCR);
vars.debt = _EBTCAmount;
// Sanity check
require(vars.netColl > 0, "BorrowerOperations: zero collateral for openCdp()!");
uint _netCollAsShares = collateral.getSharesByPooledEth(vars.netColl);
uint _liquidatorRewardShares = collateral.getSharesByPooledEth(LIQUIDATOR_REWARD);
// ICR is based on the net coll, i.e. the requested coll amount - fixed liquidator incentive gas comp.
vars.ICR = LiquityMath._computeCR(vars.netColl, vars.debt, vars.price);
// NICR uses shares to normalize NICR across CDPs opened at different pooled ETH / shares ratios
vars.NICR = LiquityMath._computeNominalCR(_netCollAsShares, vars.debt);
/**
In recovery move, ICR must be greater than CCR
CCR > MCR (125% vs 110%)
In normal mode, ICR must be greater thatn MCR
Additionally, the new system TCR after the CDPs addition must be >CCR
*/
if (isRecoveryMode) {
    _requireICRisAboveCCR(vars.ICR);
} else {
    _requireICRisAboveMCR(vars.ICR);
    uint newTCR = _getNewTCRFromCdpChange(vars.netColl, true, vars.debt, true, vars.price); // bools: coll increase, debt increase

    -
    if (vars.ICR <= BUFFERED_CCR) {
    +
    // When new TCR is worse than before, it has to be above the buffer
    +
    if (vars.ICR <= BUFFERED_CCR && newTCR < oldTCR) {
        // Any open CDP is a debt increase so this check is safe
        // If you're dragging TCR toward buffer or RM, we add an extra check for TCR
        // Which forces you to raise TCR to 135+
        _requireNewTCRisAboveBufferedCCR(newTCR);
    } else {
        _requireNewTCRisAboveCCR(newTCR);
    }
}
```
Similarly for _requireValidAdjustmentInCurrentMode(), assuming that _vars.oldTCR was populated before just as above via _vars.oldTCR = _getTCR(vars.price):
• BorrowerOperations.sol#L634-L660
```solidity
if (_isRecoveryMode) {
    // ...
} else {
    // if Normal Mode
    _requireICRisAboveMCR(_vars.newICR);
    _vars.newTCR = _getNewTCRFromCdpChange(
        // ...
    );

    -
    if ((_isDebtIncrease || _collWithdrawal > 0) && _vars.newICR <= BUFFERED_CCR) {
    +
    if ((_isDebtIncrease || _collWithdrawal > 0) && _vars.newTCR < _vars.oldTCR && _vars.newICR <= BUFFERED_CCR) {
        // Adding debt or reducing coll has negative impact on TCR, do a stricter check
        // If you're dragging TCR toward buffer or RM, we add an extra check for TCR
        // Which forces you to raise TCR to 135+
        _requireNewTCRisAboveBufferedCCR(_vars.newTCR);
    } else {
        // Other cases have a laxer check
        _requireNewTCRisAboveCCR(_vars.newTCR);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical flaw in the BorrowerOperations contract that incorrectly blocks operations which should increase the system-wide Total Collateral Ratio (TCR). After the introduction of a Buffered Critical Collateral Ratio (BCCR) the code adds an extra check: if a user’s individual collateral ratio (ICR) is at or below the buffered CCR, the contract requires the new TCR to be greater than or equal to the buffered CCR. However the condition does not verify whether the new TCR is actually lower than the previous TCR. Consequently, any operation that raises a CDP’s collateral or repays debt – actions that normally improve the protocol’s health – can be rejected when the current TCR lies between the Minimum Collateral Ratio (MCR, 125 %) and the buffered CCR (135 %). The error message emitted in these cases misleadingly states that a “TCR decreasing operation” is not permitted, even though the operation is health‑improving. This bug manifests during normal‑mode transactions such as opening a new CDP, adding collateral, withdrawing collateral together with debt repayment, or posting collateral while increasing debt. Users experience transaction reverts, see no change in their balances, and receive confusing error text, leading them to believe the protocol is malfunctioning or malicious. The issue was discovered during a security audit of the BCCR implementation, where the auditor noted that the extra TCR check was applied without comparing the new TCR to the old TCR, a pattern that would have been valid only in recovery mode where TCR must decrease. The flaw is hard to notice because the revert message appears plausible and the condition only triggers in a narrow TCR window (125‑135 %). The impact is two‑fold: from a user‑experience perspective, legitimate CDP openings and adjustments are blocked, especially for small CDPs that constitute a growing share of the user base; from a protocol‑stability perspective, the systematic denial of health‑improving actions creates downward pressure on the overall TCR, potentially compromising the safety buffer. The affected parties include CDP owners, borrowers, and the protocol itself, as the blocked operations reduce liquidity and may affect liquidation dynamics. To remediate, the buffered‑CCR check should be conditioned on the new TCR being lower than the previous TCR, i.e., enforce the extra requirement only when the operation would actually drag TCR toward the buffer. This restores the intended behavior where only genuine TCR‑decreasing actions are subject to the stricter check, allowing health‑improving transactions to succeed.
