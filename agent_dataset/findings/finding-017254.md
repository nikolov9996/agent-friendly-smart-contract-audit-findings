---
id: 17254
severity: "High"
---

# Node operator is getting slashed for full duration even though rewards are distributed based on a 14 day cycle

## Description

[contracts/contract/MinipoolManager.sol#L673-L675](https://github.com/code-423n4/2022-12-gogopool/blob/main/contracts/contract/MinipoolManager.sol#L673-L675)

A node operator sends in the amount of duration they want to stake for. Behind the scenes Rialto will stake in 14 day cycles and then distribute rewards.

If a node operator doesn’t have high enough availability and doesn’t get any rewards, the protocol will slash their staked `GGP`. For calculating the expected rewards that are missed however, the full duration is used:
    
```solidity
File: MinipoolManager.sol

557:	function getExpectedAVAXRewardsAmt(uint256 duration, uint256 avaxAmt) public view returns (uint256) {
558:		ProtocolDAO dao = ProtocolDAO(getContractAddress("ProtocolDAO"));
559:		uint256 rate = dao.getExpectedAVAXRewardsRate();
560:		return (avaxAmt.mulWadDown(rate) * duration) / 365 days; // full duration used when calculating expected reward
561:	}

...

670:	function slash(int256 index) private {

...

673:		uint256 duration = getUint(keccak256(abi.encodePacked("minipool.item", index, ".duration")));
674:		uint256 avaxLiquidStakerAmt = getUint(keccak256(abi.encodePacked("minipool.item", index, ".avaxLiquidStakerAmt")));
675:		uint256 expectedAVAXRewardsAmt = getExpectedAVAXRewardsAmt(duration, avaxLiquidStakerAmt); // full duration
676:		uint256 slashGGPAmt = calculateGGPSlashAmt(expectedAVAXRewardsAmt);
```
This is unfair to the node operator because the expected rewards is from a 14 day cycle.

Also, If they were to be unavailable again, in a later cycle, they would get slashed for the full duration once again.

## Proof of Concept

Test in `MinipoolManager.t.sol`:
    
```solidity
function testRecordStakingEndWithSlashHighDuration() public {
    uint256 duration = 365 days;
    uint256 depositAmt = 1000 ether;
    uint256 avaxAssignmentRequest = 1000 ether;
    uint256 validationAmt = depositAmt + avaxAssignmentRequest;
    uint128 ggpStakeAmt = 200 ether;

    vm.startPrank(nodeOp);
    ggp.approve(address(staking), MAX_AMT);
    staking.stakeGGP(ggpStakeAmt);
    MinipoolManager.Minipool memory mp1 = createMinipool(depositAmt, avaxAssignmentRequest, duration);
    vm.stopPrank();

    address liqStaker1 = getActorWithTokens("liqStaker1", MAX_AMT, MAX_AMT);
    vm.prank(liqStaker1);
    ggAVAX.depositAVAX{value: MAX_AMT}();

    vm.prank(address(rialto));
    minipoolMgr.claimAndInitiateStaking(mp1.nodeID);

    bytes32 txID = keccak256("txid");
    vm.prank(address(rialto));
    minipoolMgr.recordStakingStart(mp1.nodeID, txID, block.timestamp);

    skip(2 weeks); // a two week cycle
    
    vm.prank(address(rialto));
    minipoolMgr.recordStakingEnd{value: validationAmt}(mp1.nodeID, block.timestamp, 0 ether);

    assertEq(vault.balanceOf("MinipoolManager"), depositAmt);

    int256 minipoolIndex = minipoolMgr.getIndexOf(mp1.nodeID);
    MinipoolManager.Minipool memory mp1Updated = minipoolMgr.getMinipool(minipoolIndex);
    assertEq(mp1Updated.status, uint256(MinipoolStatus.Withdrawable));
    assertEq(mp1Updated.avaxTotalRewardAmt, 0);
    assertTrue(mp1Updated.endTime != 0);

    assertEq(mp1Updated.avaxNodeOpRewardAmt, 0);
    assertEq(mp1Updated.avaxLiquidStakerRewardAmt, 0);

    assertEq(minipoolMgr.getTotalAVAXLiquidStakerAmt(), 0);

    assertEq(staking.getAVAXAssigned(mp1Updated.owner), 0);
    assertEq(staking.getMinipoolCount(mp1Updated.owner), 0);

    // log slash amount
    console.log("slashedAmount",mp1Updated.ggpSlashAmt);
}
```
Slashed amount for a `365 days` duration is `100 eth` (10%). However, where they to stake for the minimum time, `14 days` the slashed amount would be only ~`3.8 eth`.

## Recommendation

Either hard code the duration to 14 days for calculating expected rewards or calculate the actual duration using `startTime` and `endTime`.

The Warden has shown an incorrect formula that uses the `duration` of the pool for slashing.

The resulting loss can be up to 26 times the yield that should be made up for.

Because the:

  * Math is incorrect
  * Based on intended usage
  * Impact is more than an order of magnitude off
  * Principal is impacted (not just loss of yield)


I believe the most appropriate severity to be High.

Base slash on validation period not full duration: [multisig-labs/gogopool#41](https://github.com/multisig-labs/gogopool/pull/41)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch in the MinipoolManager contract where the expected AVAX rewards used for calculating a GGP slash are derived from the full staking duration supplied by the node operator, while actual rewards are distributed only in fixed 14‑day cycles. The root cause is that the getExpectedAVAXRewardsAmt function multiplies the reward rate by the total duration parameter without adjusting for the shorter validation period, and the slash function later consumes this inflated expected reward amount to compute the penalty. An attacker does not need to actively exploit the code; the bug is triggered automatically when a node operator has insufficient availability and therefore earns no rewards. In that situation the protocol’s slash logic assumes the operator missed rewards for the entire requested period, inflates the expected reward figure, and consequently applies a GGP slash that can be dozens of times larger than the legitimate penalty. The impact is a severe loss of principal for the node operator – the test case shows a 365‑day pool being slashed by 100 ETH (approximately ten percent of the stake) whereas a correctly sized 14‑day pool would only lose about 3.8 ETH, a discrepancy of up to 26‑fold. This occurs whenever the slash function is called after a staking end event with zero rewards, i.e., when the operator’s availability falls below the required threshold. The affected parties are node operators who stake GGP, as well as downstream users who rely on the protocol’s correct accounting of rewards and penalties. The issue was discovered during a formal audit by Code4rena, which included a unit test that logged the slash amount for different durations and highlighted the disproportionate penalty. Because the calculation is hidden inside internal view functions, the over‑slashing can be difficult to notice without explicit testing of edge‑case durations. The recommended fix is to base the expected reward calculation on the actual validation period (the 14‑day cycle) or to hard‑code the duration constant, thereby aligning the slash amount with the true amount of missed rewards. Conceptually, this bug belongs to the class of reward‑calculation errors where time‑based parameters are mismatched, leading to incorrect penalty formulas, violation of the protocol’s economic assumptions, and user‑facing symptoms such as unexpectedly large GGP deductions and zero reward payouts despite the operator’s expectation of a modest penalty.
