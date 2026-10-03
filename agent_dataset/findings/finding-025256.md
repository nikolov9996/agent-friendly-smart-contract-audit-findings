---
id: 25256
severity: "Medium"
---

# Slashing fails when node operator doesn't have enough staked GGP

## Description



## Proof of Concept

PoC test in `MinipoolManager.t.sol`:

```javascript
	function testRecordStakingEndWithSlashNotEnoughStake() public {
		uint256 duration = 365 days;
		uint256 depositAmt = 1000 ether;
		uint256 avaxAssignmentRequest = 1000 ether;
		uint256 validationAmt = depositAmt + avaxAssignmentRequest;
		uint128 ggpStakeAmt = 100 ether; // just enough

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

		vm.prank(address(rialto)); // price changes just a bit
		oracle.setGGPPriceInAVAX(0.999 ether, block.timestamp);

		vm.prank(address(rialto));
		vm.expectRevert(); // staking cannot end because of underflow
		minipoolMgr.recordStakingEnd{value: validationAmt}(mp1.nodeID, block.timestamp, 0 ether);
	}
```

The only thing the protocol can do now is to call `recordStakingError` for the minipool, since no other state changes are allowed. This will return the staked funds but it will not slash the `GGP` amount for the node operator. Hence the node operator has evaded the slashing.

## Impact

If a node operator doesn't have enough collateral, possibly caused by price changes in `GGP` during slashing they evade slashing all together.

It's even possible for the node operator to foresee this and manipulate the price of `GGP` just prior to the period ending if they know that they are going to be slashed.

## Recommendation

If the amount to be slashed is greater than what the node operator has staked, slash all their stake.
