---
id: 25254
severity: "Medium"
---

# Any duration can be passed by node operator

## Description



## Proof of Concept

PoC test in `MinipoolManager.t.sol`:

```javascript
	function testRecordStakingEndWithSlashZeroDuration() public {
		uint256 duration = 1; // zero duration causes vault to fail on 0 amount
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

		skip(2 weeks);

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

		// very small slash amount
		assertLt(mp1Updated.ggpSlashAmt, 0.000_01 ether);
		assertGt(staking.getGGPStake(mp1Updated.owner), ggpStakeAmt - 0.000_01 ether);
	}
```

## Impact

The node operator can send in a very low `duration` to get minimize slashing amounts. It depends on the implementation in Rialto, which we cannot see. Hence submitting this.

## Recommendation

Regardless if Rialto will fail this or not, I recommend that the `duration` passed is validated to be within `14 days` and `365 days`.
