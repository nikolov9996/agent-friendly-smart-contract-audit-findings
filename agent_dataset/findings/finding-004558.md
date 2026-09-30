---
id: 4558
severity: "High"
---

# Bad Debt Redistribution Not Happening Between Liquidations in Batch Mode Submitted by 0xNirix, also found by 0xBeastBoy, santipu and 0xghOst

## Description

The issue lies in how liquidations handle debt redistribution in LiquidationManager.sol.
Here's the problematic ﬂow:
```solidity
function batchLiquidateTroves(ITroveManager troveManager, address[] memory _troveArray) public {
LiquidationValues memory singleLiquidation;
LiquidationTotals memory totals;
// First iteration round
while (troveIter < length && troveCount > 1) {
address account = _troveArray[troveIter];
uint256 ICR = troveManager.getCurrentICR(account, troveManagerValues.price);
if (ICR <= _100pct) {
singleLiquidation = _liquidateWithoutSP(troveManager, account);
} else if (ICR < troveManagerValues.MCR) {
singleLiquidation = _liquidateNormalMode(troveManager, account, debtInStabPool, sunsetting);
}
// Problem: Redistribution happens at the end of batch, not after each liquidation
_applyLiquidationValuesToTotals(totals, singleLiquidation);
}
// Redistribution only happens here, after all liquidations
troveManager.finalizeLiquidation(
msg.sender,
totals.totalDebtToRedistribute,
totals.totalCollToRedistribute,
totals.totalCollSurplus,
totals.totalDebtGasCompensation,
totals.totalCollGasCompensation
);
}
```
The problem occurs in this sequence:
1. When a CDP creates bad debt after liquidation, that debt should be redistributed immediately to update the system's state.
2. However, the redistribution is only updated at the end of the batch through finalizeLiquidation, not after each individual liquidation.
3. This means subsequent liquidations in the same batch are working with incorrect debt values because they don't account for the redistributed debt from previous liquidations in the batch.
The issue is present in batchLiquidateTroves and liquidateTroves. The consequences are:
1. Underestimated Debt:
```solidity
// The subsequent liquidations use incorrect debt values because redistribution hasn't been applied
uint256 ICR = troveManager.getCurrentICR(account, troveManagerValues.price);
// This ICR calculation uses outdated debt values
```
2. Incorrect Collateral Distribution:
```solidity
// Because debt is underestimated, more collateral than should be is marked as surplus
uint256 collSurplus = entireTroveColl - collToOffset;
if (collSurplus > 0) {
singleLiquidation.collSurplus = collSurplus;
troveManager.addCollateralSurplus(_borrower, collSurplus);
}
```
3. System-Wide Impact: Other users in the system have to cover the unaccounted debt.

## Proof of Concept

Add in LiquidtionManagerTest.t.sol
```solidity
function test_batchVsSequential_liquidation_comparison() external {
uint256 collateral1 = 1e18;
// 1 BTC
uint256 collateral2 = 2e18;
// 2 BTC
uint256 debt1 = _getMaxDebtAmount(collateral1);
uint256 debt2 = _getMaxDebtAmount(collateral2);
console.log("Debt of user 1:", debt1);
console.log("Debt of user 2:", debt2);
uint256 snapId = vm.snapshot();
// First case - Sequential Liquidations
_openTrove(users.user1, collateral1, debt1);
_openTrove(users.user2, collateral2, debt2);
mockOracle.setResponse(
mockOracle.roundId() + 1,
int256(30000 * 10 ** 8),
block.timestamp + 1,
block.timestamp + 1,
mockOracle.answeredInRound() + 1
);
vm.warp(block.timestamp + 1);
LiquidationState memory user2PreSeq = _getLiquidationState(users.user2);
// Capture events from sequential liquidations
vm.recordLogs();
liquidationMgr.liquidate(stakedBTCTroveMgr, users.user1);
Vm.Log[] memory logs1 = vm.getRecordedLogs();
LiquidationState memory user2PostFirstLiq = _getLiquidationState(users.user2);
vm.recordLogs();
liquidationMgr.liquidate(stakedBTCTroveMgr, users.user2);
Vm.Log[] memory logs2 = vm.getRecordedLogs();
// Parse sequential liquidation events
uint256 seqLiqDebt1;
uint256 seqLiqColl1;
uint256 seqLiqDebt2;
uint256 seqLiqColl2;
for (uint i = 0; i < logs1.length; i++) {
if (logs1[i].topics[0] == keccak256("Liquidation(uint256,uint256,uint256,uint256)")) {
(seqLiqDebt1, seqLiqColl1,,) = abi.decode(logs1[i].data, (uint256,uint256,uint256,uint256));
}
}
for (uint i = 0; i < logs2.length; i++) {
if (logs2[i].topics[0] == keccak256("Liquidation(uint256,uint256,uint256,uint256)")) {
(seqLiqDebt2, seqLiqColl2,,) = abi.decode(logs2[i].data, (uint256,uint256,uint256,uint256));
}
}
// Reset and do batch case
vm.revertTo(snapId);
_openTrove(users.user1, collateral1, debt1);
_openTrove(users.user2, collateral2, debt2);
mockOracle.setResponse(
mockOracle.roundId() + 1,
int256(30000 * 10 ** 8),
block.timestamp + 1,
block.timestamp + 1,
mockOracle.answeredInRound() + 1
);
vm.warp(block.timestamp + 1);
LiquidationState memory user2PreBatch = _getLiquidationState(users.user2);
// Capture events from batch liquidation
vm.recordLogs();
address[] memory troveArray = new address[](2);
troveArray[0] = users.user1;
troveArray[1] = users.user2;
liquidationMgr.batchLiquidateTroves(stakedBTCTroveMgr, troveArray);
Vm.Log[] memory batchLogs = vm.getRecordedLogs();
// Parse batch liquidation event
uint256 batchLiqDebt;
uint256 batchLiqColl;
for (uint i = 0; i < batchLogs.length; i++) {
if (batchLogs[i].topics[0] == keccak256("Liquidation(uint256,uint256,uint256,uint256)")) {
(batchLiqDebt, batchLiqColl,,) = abi.decode(batchLogs[i].data, (uint256,uint256,uint256,uint256));
}
}
// Verify liquidation states
assertEq(uint8(stakedBTCTroveMgr.getTroveStatus(users.user1)),
uint8(ITroveManager.Status.closedByLiquidation));
assertEq(uint8(stakedBTCTroveMgr.getTroveStatus(users.user2)),
uint8(ITroveManager.Status.closedByLiquidation));
// Compare sequential vs batch liquidations
console.log("Sequential Liquidation 1 - Debt:", seqLiqDebt1);
console.log("Sequential Liquidation 1 - Coll:", seqLiqColl1);
console.log("Sequential Liquidation 2 - Debt:", seqLiqDebt2);
console.log("Sequential Liquidation 2 - Coll:", seqLiqColl2);
console.log("Batch Liquidation - Total Debt:", batchLiqDebt);
console.log("Batch Liquidation - Total Coll:", batchLiqColl);
// Verify total liquidated amounts differ
assertGt(seqLiqDebt1 + seqLiqDebt2, batchLiqDebt, "Batch liquidation debt should be less than sum of sequential");
assertGt(seqLiqColl1 + seqLiqColl2, batchLiqColl, "Batch liquidation coll should be less than sum of sequential");
}
```
3.2

## Recommendation

No data

## Derived Narrative

The following field is derived content and may not be source-grounded:

During batch liquidation the contract postpones redistribution of bad debt until after all troves in the batch have been processed. The function iterates over each trove, computes the individual liquidation result and stores it in a temporary totals structure, but the call that updates the system‑wide debt and collateral state (finalizeLiquidation) is executed only once after the loop. Because the redistribution is not applied after each individual liquidation, the debt values used to calculate the next trove's collateral ratio remain stale. As a result the subsequent trove appears healthier than it actually is, leading to an underestimated debt figure and an over‑estimated collateral surplus. This accounting error allows an attacker to trigger a batch liquidation containing multiple under‑collateralised positions, extract more collateral than entitled, and leave hidden bad debt that must be absorbed by other participants. The bug manifests whenever batchLiquidateTroves or liquidateTroves is called with more than one trove in the same transaction. Borrowers, lenders and the protocol itself are affected because the protocol reports lower total bad debt while some users receive excess collateral, and the remaining users are forced to cover the undistributed debt. The issue was discovered by several auditors during a review of LiquidationManager.sol and reproduced with a test that compares sequential and batch liquidation outcomes. It is hard to notice because the liquidation completes without reverting and the incorrect numbers are only visible when aggregating results, so normal operation may appear correct. The proper fix is to apply redistribution after each individual liquidation, either by invoking the internal state‑update function inside the loop or by redesigning the accounting so that totals are updated incrementally. In abstract terms the vulnerability belongs to the class of deferred state‑update or cumulative accounting bugs where batch processing uses stale state. From a user perspective the symptoms are unexpected surplus collateral, lower reported debt, or balances that do not match the expected liquidation outcome, violating the protocol’s accounting assumptions.
