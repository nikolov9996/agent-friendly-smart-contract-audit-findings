---
id: 8357
severity: "High"
---

# Preventing token claims until vesting period ends

## Description

The g8keepVester contract, responsible for managing token vesting schedules, contains an error in its implementation that prevents users from claiming any tokens until the entire vesting period has elapsed.
The issue stems from the deploymentVest function not initializing the lastClaim timestamp when creating a new vesting schedule:
```solidity
function deploymentVest(address _deployer, uint256 _tokensToDeployer, uint256 _vestTime)
    external
    returns (uint256 vestingId)
{
    DeploymentVesting storage deploymentVesting = deploymentVestings[vestingId];
    deploymentVesting.recipient = _deployer;
    deploymentVesting.token = msg.sender;
    deploymentVesting.amount = _tokensToDeployer;
    deploymentVesting.vestingStart = uint40(block.timestamp);
    deploymentVesting.vestingEnd = uint40(block.timestamp + _vestTime); // @audit lastClaim is not set
```
This omission causes the _vested function to calculate an inflated vestedAmount:
```solidity
function _vested(uint256 _id) internal view returns (DeploymentVesting storage vesting, uint256 vestedAmount) {
    vesting = deploymentVestings[_id];
    uint256 vestingStart = vesting.vestingStart;
    if (block.timestamp < vestingStart) return (vesting, 0);
    uint256 vestingEnd = vesting.vestingEnd;
    uint256 vestingAmount = vesting.amount;
    uint256 vestingClaimed = vesting.claimed;
    if (block.timestamp >= vestingEnd) return (vesting, (vestingAmount - vestingClaimed));
    uint256 timeSinceLastClaim = block.timestamp - vesting.lastClaim; // @audit inflated since lastClaim is 0
    uint256 vestingPeriod = vestingEnd - vestingStart;
    vestedAmount = (vestingAmount * timeSinceLastClaim) / vestingPeriod; // @audit vestedAmount
```
Consequently, when a user attempts to claim tokens via the claim function, the transaction will revert due to insufficient balance, as the calculated vestedAmount exceeds the total vesting amount.

## Proof of Concept

No poc.

## Recommendation

Initialize the lastClaim timestamp in the deploymentVest function:
```solidity
function deploymentVest(address _deployer, uint256 _tokensToDeployer, uint256 _vestTime)
    external
    returns (uint256 vestingId)
{
    DeploymentVesting storage deploymentVesting = deploymentVestings[vestingId];
    deploymentVesting.recipient = _deployer;
    deploymentVesting.token = msg.sender;
    deploymentVesting.amount = _tokensToDeployer;
    deploymentVesting.vestingStart = uint40(block.timestamp);
    deploymentVesting.vestingEnd = uint40(block.timestamp + _vestTime);
    deploymentVesting.lastClaim = uint40(block.timestamp);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑initialisation error in a token vesting contract that prevents beneficiaries from receiving any tokens until the entire vesting period has elapsed. When a new vesting schedule is created the contract stores the recipient, token address, total amount, start time and end time, but it fails to set the lastClaim timestamp. The vesting calculation later reads lastClaim to determine how much time has passed since the previous claim. Because lastClaim remains zero, the expression block.timestamp‑lastClaim yields a value equal to the full elapsed time since the Unix epoch, which is far larger than the actual time since the schedule started. This inflated timeSinceLastClaim is multiplied by the total vesting amount and divided by the total vesting period, producing a vestedAmount that can exceed the total amount allocated to the schedule. When a user calls the claim function the contract attempts to transfer this oversized vestedAmount, the internal balance check fails and the transaction reverts with an insufficient‑balance error. From the user’s perspective the claim transaction always fails, the UI shows no tokens received, and the displayed balance remains unchanged even though the vesting period is still ongoing. The issue occurs immediately after any vesting schedule is deployed because the missing initialization is part of the deploymentVest function. It affects all participants who are supposed to receive vested tokens, effectively locking their funds until the contract is upgraded or the schedule reaches its end, at which point the remaining balance may be claimable. The bug was discovered during a manual audit that inspected the vesting logic and noticed that lastClaim was never written. It is easy to miss because the contract compiles and the missing field does not raise a warning, yet the arithmetic error only manifests when a claim is attempted. The vulnerability belongs to the class of incorrect state initialisation leading to faulty accounting calculations in vesting contracts. To remediate the issue the contract should initialise lastClaim to the current block timestamp when the vesting schedule is created, ensuring that timeSinceLastClaim starts from zero and the vested amount is calculated correctly over time. After this change the claim function will transfer the proportionally vested tokens as intended, restoring the expected behaviour where users receive tokens gradually according to the vesting schedule.
