---
id: 18783
severity: "High"
---

# In `LlamaRelativeQuorum`, the governance result might be incorrect as it counts the wrong approval/disapproval

## Description

In `LlamaRelativeQuorum`, the governance result might be incorrect as it counts the wrong approval/disapproval.

## Proof of Concept

The `LlamaRelativeQuorum` uses approval/disapproval thresholds that are specified as percentages of total supply and the approval/disapproval supplies are set at `validateActionCreation()` during the action creation.
```solidity
function validateActionCreation(ActionInfo calldata actionInfo) external {
  LlamaPolicy llamaPolicy = policy; // Reduce SLOADs.
  uint256 approvalPolicySupply = llamaPolicy.getRoleSupplyAsNumberOfHolders(approvalRole);
  if (approvalPolicySupply == 0) revert RoleHasZeroSupply(approvalRole);

  uint256 disapprovalPolicySupply = llamaPolicy.getRoleSupplyAsNumberOfHolders(disapprovalRole);
  if (disapprovalPolicySupply == 0) revert RoleHasZeroSupply(disapprovalRole);

  // Save off the supplies to use for checking quorum.
  actionApprovalSupply[actionInfo.id] = approvalPolicySupply;
  actionDisapprovalSupply[actionInfo.id] = disapprovalPolicySupply;
}
```
As we can see, `actionApprovalSupply` and `actionDisapprovalSupply` are set using `getRoleSupplyAsNumberOfHolders` which means the total number of role holders.

But while counting for `totalApprovals/totalDisapprovals` in `getApprovalQuantityAt()/getDisapprovalQuantityAt()`, it adds the quantity instead of role holders(1 for each holder).
```solidity
function getApprovalQuantityAt(address policyholder, uint8 role, uint256 timestamp) external view returns (uint128) {
  if (role != approvalRole && !forceApprovalRole[role]) return 0;
  uint128 quantity = policy.getPastQuantity(policyholder, role, timestamp);
  return quantity > 0 && forceApprovalRole[role] ? type(uint128).max : quantity; // @audit should return supply, not quantity
}
```
So the governance result would be wrong with the below example.

  1. There are 3 role holders(Alice, Bob, Charlie) and Alice has 2 quantities, others have 1.
  2. During the action creation with the `LlamaRelativeQuorum` strategy, `actionApprovalSupply = 3` and there should be 2 approved holders at least when `minApprovalPct = 51%`.
  3. But if Alice approves the action, the result of `getApprovalQuantityAt()` will be 2 and the action will be approved with only one approval.

It’s because `getApprovalQuantityAt()` return the quantity although `actionApprovalSupply` equals `NumberOfHolders`.

## Recommendation

`getApprovalQuantityAt()` and `getDisapprovalQuantityAt()` should return 1 instead of `quantity` for the positive quantity.

I think we can modify these functions like below.
```solidity
function getApprovalQuantityAt(address policyholder, uint8 role, uint256 timestamp) external view returns (uint128) {
  if (role != approvalRole && !forceApprovalRole[role]) return 0;
  uint128 quantity = policy.getPastQuantity(policyholder, role, timestamp);
  
  if (quantity > 1) quantity = 1;

  return quantity > 0 && forceApprovalRole[role] ? type(uint128).max : quantity;
}

function getDisapprovalQuantityAt(address policyholder, uint8 role, uint256 timestamp)
  external
  view
  returns (uint128)
{
  if (role != disapprovalRole && !forceDisapprovalRole[role]) return 0;
  uint128 quantity = policy.getPastQuantity(policyholder, role, timestamp);

  if (quantity > 1) quantity = 1;

  return quantity > 0 && forceDisapprovalRole[role] ? type(uint128).max : quantity;
}
```
This is actually how we intend this strategy to work but we’re open to feedback! Here’s an example:
  
  * An instance has 10 role holders and a 50% min approval percentage. Each role holder’s quantity is 1, so 5 role holders can approve this action.
  * 2 of the role holders have their quantity increased to 2.
  * This means that if each of these role holders cast approvals, then their approval power will count as 4. That means just one other role holder is needed to cast approval to approve the action.
  

In this system quantity can be used to provide granular approval weights to role holders.

@AustinGreen- I don’t think this make sense. Sure, if each holder’s quantity is 1, then `getRoleSupply` is same as `getRoleSupplyAsNumberOfHolders` and what you said is valid. However, if you have 10 holders each with quantity 10 at snapshot, then your `actionApprovalSupply` is set to 10 (number of holder) and any of their approval (10 quantity) would hit quorum.

@gzeon- Yes that’s exactly how the design is intended to work!

@AustinGreen- This sounds weird, is this design documented anywhere? From what I can see in the code comments it seems to be hard for anyone (including potential user/dao) to understand such logic. 
  
In the code, there is a comment

> Minimum percentage of `totalApprovalQuantity / totalApprovalSupplyAtCreationTime` required for the action to be queued

I think it is fair for one to assume `totalApprovalQuantity` and `totalApprovalSupplyAtCreationTime` would be using the same metric, instead of one using the raw count and the other using `AsNumberOfHolders`.

Although this is the intended design for this strategy, we decided to create an additional strategy that Llama instances can adopt that follows the warden’s recommendations. It uses total (dis)approval quantity for the quorum calculation as specified.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the LlamaRelativeQuorum strategy calculates voting power for approval and disapproval. The contract records the total approval and disapproval supply at action creation by calling getRoleSupplyAsNumberOfHolders, which returns the raw count of role holders. However, when the actual votes are tallied, the functions getApprovalQuantityAt and getDisapprovalQuantityAt return the raw quantity associated with each holder, which can be greater than one when a holder has been granted additional weight. This mismatch means that the numerator (total approvals) is measured in weighted units while the denominator (total supply) is measured in simple headcount. As a result, a single holder with a quantity greater than one can satisfy a quorum that was intended to require a majority of distinct holders. The bug can be exploited by an attacker who holds a higher quantity: by casting a single weighted approval they can trigger the condition totalApprovalQuantity/totalApprovalSupplyAtCreationTime ≥ minApprovalPct, causing an action to be queued even though the required percentage of distinct holders has not voted. The impact is that governance decisions may be approved with far fewer participants than intended, undermining the security and trust model of the DAO, potentially allowing malicious proposals to pass and exposing funds to unauthorized actions. The issue manifests whenever the policy assigns quantities greater than one to any role holder while the relative quorum strategy is used; it does not appear when all quantities are exactly one. Affected parties include all DAO participants, the protocol’s governance layer, and any assets that can be moved by approved actions. The problem was discovered during a manual audit that compared the supply calculation in validateActionCreation with the vote‑counting logic and noticed the inconsistent metric. It is subtle because both functions appear to return a “quantity” and the code comments refer to percentages, leading reviewers to assume the same unit is used on both sides. From a user’s perspective the symptom is that an action becomes approved after only one vote, even though the UI or documentation indicates that a majority of holders is required; users may see an unexpected “action queued” message or a proposal passing with an apparently insufficient number of approvals. The correct fix is to align the metrics: either change getApprovalQuantityAt and getDisapprovalQuantityAt to return a constant value of 1 for any positive quantity (or the maximum value for forced roles) so that each holder contributes a single unit, or modify the supply calculation to use the total weighted quantity instead of the raw holder count. This ensures that the percentage comparison uses a consistent denominator and numerator, restoring the intended quorum semantics.
