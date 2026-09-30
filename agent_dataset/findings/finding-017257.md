---
id: 17257
severity: "High"
---

# MinipoolManager: node operator can avoid being slashed

## Description

When staking is done, a Rialto multisig calls `MinipoolManager.recordStakingEnd` (https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L385-L440).

If the `avaxTotalRewardAmt` has the value zero, the `MinipoolManager` will slash the node operator’s GGP.

The issue is that the amount to slash can be greater than the GGP balance the node operator has staked.

This will cause the call to `MinipoolManager.recordStakingEnd` to revert because an underflow is detected.

This means a node operator can create a minipool that cannot be slashed.

A node operator must provide at least 10% of `avaxAssigned` as collateral by staking GGP.

It is assumed that a node operator earns AVAX at a rate of 10% per year.

So if a Minipool is created with a duration of `> 365 days`, the 10% collateral is not sufficient to pay the expected rewards.

This causes the function call to revert.

Another cause of the revert can be that the GGP price in AVAX changes. Specifically if the GGP price falls, there needs to be slashed more GGP.

Therefore if the GGP price drops enough it can cause the call to slash to revert.

I think it is important to say that with any collateralization ratio this can happen. The price of GGP must just drop enough or one must use a long enough duration.

The exact impact of this also depends on how the Rialto multisig handles failed calls to `MinipoolManager.recordStakingEnd`.

It looks like if this happens, `MinipoolManager.recordStakingError` (https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L484-L515) is called.

This allows the node operator to withdraw his GGP stake.

So in summary a node operator can create a Minipool that cannot be slashed and probably remove his GGP stake when it should have been slashed.

## Proof of Concept

When calling `MinipoolManager.recordStakingEnd` (https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L385-L440) and the `avaxTotalRewardAmt` parameter is zero, the node operator is slashed:

```solidity
// No rewards means validation period failed, must slash node ops GGP.
if (avaxTotalRewardAmt == 0) {
    slash(minipoolIndex);
}
```

The `MinipoolManager.slash` function (https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L670-L683) then calculates `expectedAVAXRewardsAmt` and from this `slashGGPAmt`:

```solidity
uint256 avaxLiquidStakerAmt = getUint(keccak256(abi.encodePacked("minipool.item", index, ".avaxLiquidStakerAmt")));
uint256 expectedAVAXRewardsAmt = getExpectedAVAXRewardsAmt(duration, avaxLiquidStakerAmt);
uint256 slashGGPAmt = calculateGGPSlashAmt(expectedAVAXRewardsAmt);
```

Downstream there is then a revert due to underflow because of the following line in `Staking.decreaseGGPStake` (https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/Staking.sol#L94-L97):

```solidity
subUint(keccak256(abi.encodePacked("staker.item", stakerIndex, ".ggpStaked")), amount);
```

You can add the following foundry test to `MinipoolManager.t.sol`:

```solidity
function testRecordStakingEndWithSlashFail() public {
    uint256 duration = 366 days;
    uint256 depositAmt = 1000 ether;
    uint256 avaxAssignmentRequest = 1000 ether;
    uint256 validationAmt = depositAmt + avaxAssignmentRequest;
    uint128 ggpStakeAmt = 100 ether;

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

    vm.startPrank(address(rialto));

    skip(duration);

    minipoolMgr.recordStakingEnd{value: validationAmt}(mp1.nodeID, block.timestamp, 0 ether);
}
```

See that it runs successfully with `duration = 365 days` and fails with `duration = 366 days`.

The similar issue occurs when the GGP price drops. I chose to implement the test with `duration` as the cause for the underflow because your tests use a fixed AVAX/GGP price.

## Recommendation

You should check if the amount to be slashed is greater than the node operator’s GGP balance. If this is the case, the amount to be slashed should be set to the node operator’s GGP balance.

I believe this check can be implemented within the `MinipoolManager.slash` function without breaking any of the existing accounting logic.

```solidity
function slash(int256 index) private {
    address nodeID = getAddress(keccak256(abi.encodePacked("minipool.item", index, ".nodeID")));
    address owner = getAddress(keccak256(abi.encodePacked("minipool.item", index, ".owner")));
    uint256 duration = getUint(keccak256(abi.encodePacked("minipool.item", index, ".duration")));
    uint256 avaxLiquidStakerAmt = getUint(keccak256(abi.encodePacked("minipool.item", index, ".avaxLiquidStakerAmt")));
    uint256 expectedAVAXRewardsAmt = getExpectedAVAXRewardsAmt(duration, avaxLiquidStakerAmt);
    uint256 slashGGPAmt = calculateGGPSlashAmt(expectedAVAXRewardsAmt);
    setUint(keccak256(abi.encodePacked("minipool.item", index, ".ggpSlashAmt")), slashGGPAmt);

    emit GGPSlashed(nodeID, slashGGPAmt);

    Staking staking = Staking(getContractAddress("Staking"));

    if (slashGGPAmt > staking.getGGPStake(owner)) {
        slashGGPAmt = staking.getGGPStake(owner);
    }
    
    staking.slashGGP(owner, slashGGPAmt);
}
```

This is a combination of two other issues from other wardens

  1. Slash amount shouldn’t depend on duration: https://github.com/code-423n4/2022-12-gogopool-findings/issues/694
  2. GGP Slash shouldn’t revert: https://github.com/code-423n4/2022-12-gogopool-findings/issues/743

This finding combines 2 issues:

  * If price drops Slash can revert -> Medium
  * Attacker can set Duration to too high to cause a revert -> High

Am going to dedupe this and the rest, but ultimately I think these are different findings, that should have been filed separately.

The Warden has shown how a malicious staker could bypass slashing, by inputting a duration that is beyond the intended amount.

Other reports have shown how to sidestep the slash or reduce it, however, this report shows how the bypass can be enacted maliciously to break the protocol functionality, to the attacker’s potential gain.

Because slashing is sidestepped in it’s entirety, I believe this finding to be of High Severity.

If staked GGP doesn’t cover slash amount, slash it all: [multisig-labs/gogopool#41](https://github.com/multisig-labs/gogopool/pull/41)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the MinipoolManager contract where the logic that determines how much GGP a node operator must be slashed can produce a value that exceeds the operator’s actual GGP stake. The contract assumes that a node operator provides at least ten percent of the AVAX assigned as collateral and that the GGP price remains relatively stable. When the staking period ends, the Rialto multisig calls recordStakingEnd. If the avaxTotalRewardAmt parameter is zero, the contract proceeds to calculate an expected AVAX reward based on the pool duration and then converts that amount into a GGP slash amount. Because the calculation does not verify that the operator’s GGP balance is sufficient, two situations can cause the slash amount to be larger than the available stake: (1) the minipool is created with a duration longer than one year, making the ten‑percent collateral insufficient to cover the expected rewards, and (2) a significant drop in the GGP‑to‑AVAX price increases the required GGP to cover the same AVAX reward. When the slash function attempts to deduct more GGP than the operator holds, the underlying Staking contract triggers an underflow check and reverts the transaction. The revert prevents the slash from being applied, allowing the node operator to avoid any penalty and later withdraw the full GGP stake through the recordStakingError path. From a user’s perspective the transaction simply fails with a revert, the node operator sees no slash event, and the protocol’s accounting shows an unchanged GGP balance even though a penalty should have been applied. The issue was uncovered during a formal audit by reproducing the failure with a test that uses a duration of 366 days, causing the slash to revert, and by reasoning about price‑impact scenarios. It is hard to notice because the revert only occurs under specific edge‑case parameters and the contract does not emit a clear error explaining the underflow. The bug belongs to the class of “incorrect slashing calculation leading to arithmetic underflow” and violates the protocol’s economic assumptions that penalties are always enforceable. The recommended mitigation is to add a safeguard that caps the slash amount to the operator’s actual GGP balance before attempting the deduction, or to redesign the collateral model so that the required GGP is always sufficient regardless of duration or price fluctuations.
