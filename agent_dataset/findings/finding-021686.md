---
id: 21686
severity: "High"
---

# Slashing `NativeVault` will lead to locked ETH for the users

## Description

The Karak protocol includes a slashing mechanism that allows the contract owner to penalize stakers by reducing their staked assets in the event of malicious activity by the operator. If a user with a staked balance of 32 ETH is subject to a 3 ETH slashing, they should ideally be able to withdraw the remaining 29 ETH. However, due to a flaw in the implementation, when the user attempts to fully withdraw their ETH, they are only able to withdraw less than the actual remaining amount, with some ETH becoming permanently locked in the protocol.

Specifically, if all share tokens are burned during the withdrawal process, the user cannot access the remaining locked ETH. This results in users receiving fewer ETH than they are entitled to, with the excess ETH becoming inaccessible and permanently locked within the protocol.

## Proof of Concept

Consider the following simplified scenario, where Alice want to restake her 32 ETH into Karak protocol, using 1 validator and no rewards acumulated for simplicity. In this example, although Alice initially had 32 ETH staked and should be able to withdraw 29 ETH (after a 3 ETH slashing), she ends up receiving only 26 ETH. The remaining 3 ETH becomes permanently locked in the contract. The steps she need to perform are the following:

  1. Staking and Initial Setup:

     * Alice call `createNode` to point her withdrawal credentials to it
     * She then calls `validateWithdrawalCredentials` followed by `startSnapshot` and `validateSnapshotProofs`. _After these actions, the state will look like this:  
     `totalAssets = 32e18`  
     `totalSupply = 32e18`  
     `totalRestakedETH = 32e18` (in her Node struct)_
  2. Slashing:

     * A slashing event occurs for 3 ETH, reducing the `totalAssets` to `29e18`.
  3. Withdraw from Beacon Chain:

     * Alice decides to withdraw all her ETH from the Beacon Chain, resulting in her node balance being 32 ETH.
     * To withdraw her ETH from the node, she performs the following operations: `startSnapshot`, `validateSnapshotProofs`, `startWithdraw`, and `finishWithdraw`.
  4. Starting Snapshot

     * When `startSnapshot` is executed, `_transferToSlashStore` is called, slashing 3 ETH from her node and transferring them to `SlashStore`. This reduces `totalRestakedETH` to `29e18` in her Node struct and saves the new snapshot with `nodeBalanceWei = 29e18`.
  5. Validate snapshot proofs

     * Alice calls `validateSnapshotProofs` to validate her balance proofs:

     ```solidity
                int256 balanceDeltaWei = self.validateSnapshotProof(
                    nodeOwner, validatorDetails, balanceContainer.containerRoot, balanceProofs[i]
                );
     ```

     * `balanceDeltaWei = -32e18` (the difference between `newBalanceWei` of 0 and `prevBalanceWei` of 32e18)
     * `snapshot.remainigProofs = 0` since Alice has only one validator
     * After validation `_updateSnapshot` finalize snapshot due to no remaining active validators, where the balance of the user will be decreased due to the following calculation:

     ```solidity
     int256 totalDeltaWei = int256(snapshot.nodeBalanceWei) + snapshot.balanceDeltaWei;
     ```

     * This results in `29e18 - 32e18 = -3e18`, reducing Alice’s shares by 3e18. The state after execution will be:  
     `node.totalRestakedETH: 26e18`  
     `node.withdrawableCreditedNodeETH: 29e18`  
     `balanceOf(alice) = 28689655172413793104`  
     `totalAssets = 26e18`  
     `totalSupply = 28689655172413793104`
     * Starting Withdrawal

     * Alice calls `startWithdraw`. There is a check to prevent a user from withdrawing more than they actually can, but in Alice’s situation, it will be less than what she should withdraw:

     ```solidity
            if (weiAmount > withdrawableWei(msg.sender) - self.nodeOwnerToWithdrawAmount[msg.sender]) {
                revert WithdrawMoreThanMax();
            }
     ```

     * `withdrawableWei(msg.sender)` will return the minimum between:

     ```solidity
     function withdrawableWei(address nodeOwner) public view nodeExists(nodeOwner) returns (uint256) {
             return
                 Math.min(convertToAssets(balanceOf(nodeOwner)), _state().ownerToNode[nodeOwner].withdrawableCreditedNodeETH);
         }
     ```

     * `convertToAssets` is calculated as:

     `(shares * (totalAssets + 1)) / (totalSupply + 1)` which is:  
     `(28689655172413793104 * (26e18 + 1)) / (28689655172413793104 + 1) = 26e18` while  
     `_state().ownerToNode[nodeOwner].withdrawableCreditedNodeETH` is 29e18 (the actual withdrawable wei after slashing)

  7. Finishing Withdrawal:

     * `finishWithdrawal` sends the maximum withdrawableWei (26e18) to Alice, burning all her tokens and causing 3 ETH to remain stuck in the node.

## Recommendation

Due to the complexity and the current limitations in testing the implementation of the slashing mechanism, a precise fix is difficult to pinpoint. In the example provided above, the problem occurs at step 5 where `_decreaseBalance` is called again reducing the `totalAssets` by another `3e18` (the slashed amount). If `totalAssets` are not decreased again and stays `29e18` in the next step, `withdrawableWei(msg.sender)` would correctly return the minimum between `28999999999999999999` and `29000000000000000000`.

However, to address the root cause of the issue, a better mechanism for handling slashing should be implemented and tested.

> Great find!
>
> The crux of this issue is that `nodeBalanceWei` is calculated _after_ `_transferToSlashStore()` is called, so `node.nodeAddress.balance` will have already decreased before the unattributed balance can be added to `totalRestakedETH`.
>
> This causes a loss of funds for the node owner as he does not receive shares for the unattributed balance that was lost, as such, I believe high severity is appropriate.

> This mitigation only burns the ETH that has already been credited to the user consequently avoiding this scenario.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting flaw in the Karak protocol's slashing and withdrawal logic that can permanently lock a portion of a staker's ETH. When a validator is slashed, the contract correctly reduces the total assets by the slashed amount, but later, during the snapshot and withdrawal sequence, the implementation calls the balance‑decreasing function a second time. This second reduction is applied after the node balance has already been adjusted and after share tokens have been burned, causing the internal totalAssets value to be lower than the actual ETH that remains in the node. As a result the function that computes the maximum withdrawable amount (withdrawableWei) returns the minimum of two values: the converted share balance and a stored withdrawableCreditedNodeETH. Because totalAssets has been decreased twice, the converted share balance is calculated as a smaller number, so the contract allows the user to withdraw less ETH than they are entitled to. In the example, a user with 32 ETH who is slashed by 3 ETH can only withdraw 26 ETH, while the remaining 3 ETH stays locked forever because the user’s share tokens are burned and there is no path to redeem the excess balance. The bug manifests only when a user attempts a full withdrawal after a slashing event and all their share tokens are burned in the same transaction. It affects any staker who relies on the protocol to return their remaining stake after a slash, leading to unexpected loss of funds, zero or reduced balances in the UI, and a breach of the protocol’s accounting guarantees. The issue was discovered during a Code4rena audit by tracing the slashing flow and noticing that nodeBalanceWei is calculated after the transfer to the slash store, causing the unattributed balance to be omitted from totalRestakedETH. The problem is subtle because the contract still reports a non‑zero withdrawable amount, so users may not immediately realize that part of their ETH is unrecoverable. The proper fix is to avoid decreasing totalAssets a second time after slashing, or to redesign the slashing accounting so that the node’s balance is recorded before any share burn and the withdrawableCreditedNodeETH reflects the true remaining ETH. In short, the bug is an accounting/logic error that violates the expected invariant that totalAssets equals the sum of all user balances, resulting in funds disappearing from the user’s perspective.
