---
id: 13959
severity: "High"
---

# NativeVault._startSnapshot() reverts with an arithmetic underflow when a native nodes balance decreases

## Description

node.creditedNodeETH stores the cumulative amount of ETH ever held by the native node as it is increased in _updateSnapshot() by nodeBalanceWei:
```solidity
node.creditedNodeETH += snapshot.nodeBalanceWei;
```
Note that node.creditedNodeETH is not modified anywhere else in the code.
node.creditedNodeETH is used in _startSnapshot() to calculate the amount of ETH gained by the native node since the last snapshot:
```solidity
// Calculate unattributed node balance
uint256 nodeBalanceWei = node.nodeAddress.balance - node.creditedNodeETH;
```
However, when the native node transfers ETH out, its ETH balance will become smaller than node.creditedNodeETH. Afterwards, when _startSnapshot() is called, node.nodeAddress.balance - node.creditedNodeETH will revert with an underflow.
For example:
• Assume a native node holds 2 ETH. Both nodeAddress.balance and creditedNodeETH are 2e18.
• The node owner withdraws 1 ETH, which transfers 1 ETH out from the native node.
• When _startSnapshot() is called afterwards:
– nodeAddress.balance - creditedNodeETH = 1e18 - 2e18, which reverts with an underflow.
This makes it impossible for the node owner's snapshot to ever be updated. As such, his number of shares will never increase even if his total restaked balance increases from ETH rewards.

## Proof of Concept

no poc

## Recommendation

creditedNodeETH should store the native node's ETH balance during the last snapshot.
In _updateSnapshot(), consider removing the line adding nodeBalanceWei to creditedNodeETH:
```solidity
- node.creditedNodeETH += snapshot.nodeBalanceWei;
```
Instead, set creditedNodeETH to the node's current balance in _startSnapshot(). Additionally, nodeBalanceWei should be 0 when the native node's ETH balance decreases:
```solidity
// Calculate unattributed node balance
- uint256 nodeBalanceWei = node.nodeAddress.balance - node.creditedNodeETH;
+ uint256 nodeBalanceWei;
+ if (node.nodeAddress.balance > node.creditedNodeETH) {
+ nodeBalanceWei = node.nodeAddress.balance - node.creditedNodeETH;
+ }
+ node.creditedNodeETH = node.nodeAddress.balance;
```
This ensures nodeBalanceWei will always be the amount of ETH received by the native node after the last snapshot.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the snapshot routine of a native staking vault where the contract keeps a cumulative record of the total ether ever held by a node, called creditedNodeETH. This variable is increased each time a snapshot is taken by adding the node's current balance, but it is never decreased when the node withdraws ether. Consequently, when the node’s external address balance becomes lower than the stored creditedNodeETH, the calculation of the unattributed node balance performed in _startSnapshot() – nodeAddress.balance minus creditedNodeETH – triggers a checked arithmetic underflow and the transaction reverts. The root cause is the misuse of a cumulative accounting field for a value that should represent the balance at the last snapshot, combined with Solidity’s default overflow/underflow protection. An attacker or any honest node owner can exploit the bug simply by withdrawing ether and then invoking the next snapshot; the underflow prevents the snapshot from completing, which means the node’s share count is never updated and any subsequent reward accrual is effectively blocked. The impact is that node owners see no increase in their share balance despite earning rewards, leading to missing or delayed payouts and a break in the protocol’s accounting guarantees. The condition occurs whenever a native node’s balance decreases after a previous snapshot – for example, after a withdrawal of 1 ETH from a node that previously held 2 ETH, the subtraction 1 ETH – 2 ETH underflows and reverts. Affected parties include the node owners, the protocol’s reward distribution mechanism, and any participants relying on accurate share calculations. The issue was discovered during a manual audit of the Karak Native Restaking contract, where the auditor observed that the snapshot function could revert under certain balance changes. It is hard to notice because the subtraction looks innocuous and only fails after a specific state transition that may not be covered by typical unit tests. To remediate, the contract should store the node’s balance at the time of the last snapshot rather than a cumulative total, update creditedNodeETH to the current balance each snapshot, and guard the subtraction with a conditional check so that nodeBalanceWei is set to zero when the balance has decreased. This change restores correct accounting, ensures that shares can increase after rewards are earned, and eliminates the underflow risk. In user‑facing terms, after withdrawing ether a node owner may see the UI report that no new shares are minted, rewards appear to be missing, or transactions fail with a generic revert error, contrary to the expectation that withdrawing funds should not stop future reward accrual.
