---
id: 17252
severity: "High"
---

# AVAX Assigned High Water is updated incorrectly

## Description

[contracts/contract/MinipoolManager.sol#L374](https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L374)

Node operators can manipulate the assigned high water to be higher than the actual.

## Proof of Concept

The protocol rewards node operators according to the `AVAXAssignedHighWater` that is the maximum amount assigned to the specific staker during the reward cycle.

In the function `MinipoolManager.recordStakingStart()`, the `AVAXAssignedHighWater` is updated as below.
    
```solidity
MinipoolManager.sol
349: 	function recordStakingStart(
350: 		address nodeID,
351: 		bytes32 txID,
352: 		uint256 startTime
353: 	) external {
354: 		int256 minipoolIndex = onlyValidMultisig(nodeID);
355: 		requireValidStateTransition(minipoolIndex, MinipoolStatus.Staking);
356: 		if (startTime > block.timestamp) {
357: 			revert InvalidStartTime();
358: 		}
359:
360: 		setUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".status")), uint256(MinipoolStatus.Staking));
361: 		setBytes32(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".txID")), txID);
362: 		setUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".startTime")), startTime);
363:
364: 		// If this is the first of many cycles, set the initialStartTime
365: 		uint256 initialStartTime = getUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".initialStartTime")));
366: 		if (initialStartTime == 0) {
367: 			setUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".initialStartTime")), startTime);
368: 		}
369:
370: 		address owner = getAddress(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".owner")));
371: 		uint256 avaxLiquidStakerAmt = getUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".avaxLiquidStakerAmt")));
372: 		Staking staking = Staking(getContractAddress("Staking"));
373: 		if (staking.getAVAXAssignedHighWater(owner) < staking.getAVAXAssigned(owner)) {
374: 			staking.increaseAVAXAssignedHighWater(owner, avaxLiquidStakerAmt);//@audit wrong
375: 		}
376:
377: 		emit MinipoolStatusChanged(nodeID, MinipoolStatus.Staking);
378: 	}
```
In the line #373, if the current assigned AVAX is greater than the owner’s `AVAXAssignedHighWater`, it is increased by `avaxLiquidStakerAmt`. But this is supposed to be updated to `staking.getAVAXAssigned(owner)` rather than being increased by the amount.

Example: The node operator creates a minipool with 1000AVAX via `createMinipool(nodeID, 2 weeks, delegationFee, 1000*1e18)`.  
On creation, the assigned AVAX for the operator will be 1000AVAX.  
If the Rialtor calls `recordStakingStart()`, `AVAXAssignedHighWater` will be updated to 1000AVAX. After the validation finishes, the operator creates another minipool with 1500AVAX this time. Then on `recordStakingStart()`, `AVAXAssignedHighWater` will be updated to 2500AVAX by increasing 1500AVAX because the current assigned AVAX is 1500AVAX which is higher than the current `AVAXAssignedHighWater=1000AVAX`.  
This is wrong because the actual highest assigned amount is 1500AVAX.  
Note that `AVAXAssignedHighWater` is reset only through the function `calculateAndDistributeRewards` which can be called after `RewardsCycleSeconds=28 days`.

## Recommendation

Call `staking.resetAVAXAssignedHighWater(owner)` instead of calling `increaseAVAXAssignedHighWater()`.
    
```solidity
MinipoolManager.sol
373: 		if (staking.getAVAXAssignedHighWater(owner) < staking.getAVAXAssigned(owner)) {
374: 			staking.resetAVAXAssignedHighWater(owner); //@audit update to the current AVAX assigned
375: 		}
```
Can we take some extra considerations here please?  
Discussed with @0xju1ie (GoGoPool) about this specific issue, and this was the answer:

(it is AVAXAssignedHighWater)
    
    It increases on a per minipool basis right now, increasing based on only what that single minipool is getting. 
    If it was to just update the AVAXAssignedHighWater to getAVAXAssigned, then it could be assigning the highwater mark too early.
    
    EX for how it is now:
    1. create minipool1, assignedAvax = 1k, high water= 0
    2. create minipool2, assignedAvax =1k, high water = 0
    3. record start for minipool1, highwater -> 1k
    4. record start for minipool2, highwater -> 2k
    
    EX for how your suggestion could be exploited:
    1. create minipool1, assignedAvax = 1k, high water= 0
    2. create minipool2, assignedAvax =1k, high water = 0
    3. record start for minipool1, highwater -> 2k
    4. cancel minipool2, highwater -> 2k
    
    if we used only avax assigned for that case then it would mess up the collateralization ratio for the second minipool and they would only get paid for the minipool that they are currently operating, not the one that ended previously. 

Their example in the proof of concept section is correct, and we have decided that this is not the ideal behavior and thus this is a bug. However, their recommended mitigation steps would create other issues, as highlighted by what @Franfran said. We intend to solve this issue differently than what they suggested.

The Warden has shown a flaw in the way `increaseAVAXAssignedHighWater` is used, which can be used to:

  * Inflate the amount of AVAX
  * With the goal of extracting more rewards than intended


I believe that the finding highlights both a way to extract further rewards as well as broken accounting.

For this reason I agree with High Severity.

New variable to track validating avax: [multisig-labs/gogopool#25](https://github.com/multisig-labs/gogopool/pull/25)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incorrect accounting mechanism for the AVAXAssignedHighWater value used by the GoGoPool protocol to determine the maximum amount of AVAX assigned to a node operator during a reward cycle. The root cause is the use of the function increaseAVAXAssignedHighWater with the liquid AVAX amount of a newly started minipool (avaxLiquidStakerAmt) when the current high‑water mark is lower than the operator’s total assigned AVAX. Instead of resetting the high‑water to the current total assigned amount, the code adds the new minipool amount to the existing high‑water, causing the high‑water to exceed the true maximum assigned AVAX. This can be exploited by a node operator who creates multiple minipools and controls the order in which recordStakingStart is called, inflating the high‑water value and consequently the reward calculation that uses this value as a cap. For example, an operator can start a first minipool of 1,000 AVAX, then a second of 1,500 AVAX; the buggy logic will raise the high‑water to 2,500 AVAX even though the actual highest assigned amount is only 1,500 AVAX. Because the high‑water is never decreased, even cancelling a minipool does not correct the inflated value. The impact is that the protocol may distribute more rewards than it should, leading to over‑payment, loss of funds for other participants, and a broken collateralisation ratio for subsequent minipools. The issue manifests when recordStakingStart is executed and the condition staking.getAVAXAssignedHighWater(owner) < staking.getAVAXAssigned(owner) holds; under these conditions the contract incorrectly calls increaseAVAXAssignedHighWater. The bug was discovered during a Code4rena audit, where the auditors observed that the high‑water update logic could be manipulated to inflate rewards. It is hard to notice because the high‑water value only ever increases, matching the expectation that assigned AVAX grows over time, and the discrepancy appears only in the reward distribution phase after a full cycle. To fix the issue, the contract should replace the increase call with a reset to the current total assigned AVAX (e.g., staking.resetAVAXAssignedHighWater(owner) or directly setting the high‑water to staking.getAVAXAssigned(owner)), ensuring the high‑water never exceeds the actual maximum assigned amount and that it is only updated when the true peak changes. This correction restores proper accounting, prevents reward inflation, and aligns the protocol’s business logic with its intended financial guarantees.
