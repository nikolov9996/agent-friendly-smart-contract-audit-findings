---
id: 25577
severity: "Crit/High"
---

# ETH withdrawals from EigenLayer always fail due to OperatorDelegator's nonReentrant receive()

## Description



## Proof of Concept

To prove the concept, it's sufficient to upgrade `OperatorDelegator` on a mainnet fork and initiate a withdrawal that has ETH among the withdrawn strategies.

While it would be too bulky to provide a coded PoC, you can find in [this GH Gist](<https://gist.github.com/assets/145972240/0f2500e1-1f93-4daf-8a5f-509da79f2e96>) the Foundry traces of such failed call on a mainnet fork.

## Vulnerability details

The [`OperatorDelegator.completeQueuedWithdrawal()`](<https://github.com/code-423n4/2024-04-renzo/blob/519e518f2d8dec9acf6482b84a181e403070d22d/contracts/Delegation/OperatorDelegator.sol#L265>) function is used by admins to finalize previously initiated withdraws of shares from EigenLayer.

We note that both this and the OperatorDelegator's `receive()` functions are `nonReentrant`:

```Solidity
File: OperatorDelegator.sol
265:     function completeQueuedWithdrawal(
266:         IDelegationManager.Withdrawal calldata withdrawal,
267:         IERC20[] calldata tokens,
268:         uint256 middlewareTimesIndex
269:     ) external nonReentrant onlyNativeEthRestakeAdmin {
270:         uint256 gasBefore = gasleft();
271:         if (tokens.length != withdrawal.strategies.length) revert MismatchedArrayLengths();
272:
273:         // complete the queued withdrawal from EigenLayer with receiveAsToken set to true
274:         delegationManager.completeQueuedWithdrawal(withdrawal, tokens, middlewareTimesIndex, true);
---
501:     receive() external payable nonReentrant {
502:         // check if sender contract is EigenPod. forward full withdrawal eth received
503:         if (msg.sender == address(eigenPod)) {
504:             restakeManager.depositQueue().forwardFullWithdrawalETH{ value: msg.value }();
```

However, the `receive()` function is normally called by the `EigenPod` in the call stack originated by the L274 `completeQueuedWithdrawal()` when `receiveAsTokens == true` like in this case. This particular instance of reentrancy is not only acceptable but also required to allow ETH redemptions from EigenLayer. However, the `nonReentrant` modifier prevents it.

## Impact

All withdrawals that include any amount of ETH will be permanently stuck in EigenLayer and won't be redeemable. Only amounts coming from new deposits can be redeemed and the team will have no way to fill the withdrawal queues. To unblock them, the team will necessarily have to upgrade `OperatorDelegator`.

## Recommendation

Consider removing `nonReentrant` from OperatorDelegator's `receive`, or applying the modifier only in case `msg.sender != eigenPod`.
