---
id: 14462
severity: "High"
---

# Lost Funds Due To Specifying Wrong ETH Address In completeQueuedWithdrawal

## Description

Specifying a token from another queued withdrawal while withdrawing from beaconChainETHStrategy results in accounting errors that prevents the completion of that queued withdrawal.
EigenLayer’s DelegationManager::completeQueuedWithdrawal() function takes in an array of tokens that correspond to all the strategies that are being withdrawn from. These token addresses are checked to ensure that they match with the strategy in StrategyBase::_beforeWithdrawal():
```solidity
function _beforeWithdrawal(address recipient, IERC20 token, uint256 amountShares) internal virtual {
    require(token == underlyingToken, "StrategyBase.withdraw: Can only withdraw the strategy token");
}
```
These token addresses are also used in Renzo to decrement the queuedShares mapping for each corresponding token in OperatorDelegator::completeQueuedWithdrawal():
```solidity
for (uint256 i; i < tokens.length; ) {
    if (address(tokens[i]) == address(0)) revert InvalidZeroInput();
    // deduct queued shares for tracking TVL
    queuedShares[address(tokens[i])] -= withdrawal.shares[i];
}
```
However, EigenLayer ignores the provided token address when withdrawing from the beaconChainETHStrategy, allowing the ETH withdrawal to complete with any token address as input. This allows a native ETH restake admin through malicious intent or user error to decrement the queued shares of another queued withdrawal token instead, resulting in an underﬂow error that would prevent further token withdrawal of that token type from being completed, and hence causing the withdrawn funds to be irrecoverably lost.

## Proof of Concept

no poc

## Recommendation

Consider adding the following check to make sure that only the IS_NATIVE address can be used for beaconChainETHStrategy withdrawals:
```solidity
if (address(tokens[i]) != IS_NATIVE) {
    if (withdrawal.strategies[i] == delegationManager.beaconChainETHStrategy()) {
        revert IncorrectStrategy();
    }
}
```
Restaking Smart Contract Review

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the withdrawal completion routine of EigenLayer’s DelegationManager, specifically the completeQueuedWithdrawal function that processes an array of token addresses supplied by the caller. For most strategies the function validates that each supplied token matches the underlying token of the strategy by invoking StrategyBase._beforeWithdrawal, which contains a require statement that the token argument equals the strategy’s underlyingToken. However, when the withdrawal targets the beaconChainETHStrategy – the native ETH restake strategy – the implementation deliberately skips this validation and accepts any token address. The supplied token addresses are later used in OperatorDelegator.completeQueuedWithdrawal to decrement the queuedShares mapping for each token, assuming the token corresponds to the withdrawal being processed. Because the check is omitted for the native ETH strategy, a caller can provide an arbitrary token address, causing the contract to subtract the shares of a different queued withdrawal from the wrong token’s queuedShares entry. This creates an accounting under‑flow: the queuedShares entry for the unrelated token becomes negative (or reverts), preventing any future withdrawals of that token type and effectively locking the associated funds. The bug can be triggered either by a malicious admin who intentionally supplies a wrong address or by an honest user who mistakenly passes an incorrect token identifier. From the user’s perspective the expected outcome – a successful ETH withdrawal – is observed, but subsequent attempts to withdraw the affected token either return zero or fail with an error, leading to the impression that “my funds disappeared” or “the refund is missing”. The issue was uncovered during a security audit (SigmaPrime) that examined the logical flow of completeQueuedWithdrawal and noticed the missing token verification for the native ETH strategy. It is subtle because the function otherwise behaves correctly for all other strategies, and the failure only manifests when a specific combination of token array and strategy is used, making it easy to overlook during routine testing. The root cause is the absence of a guard that enforces the use of the special IS_NATIVE sentinel address when withdrawing from the beaconChainETHStrategy. To remediate the problem the contract should add an explicit check that rejects any token address other than IS_NATIVE for this strategy, reverting with a clear error such as IncorrectStrategy. This restores the invariant that queuedShares are only decremented for the token actually being withdrawn, preserving accounting integrity and preventing irreversible loss of funds.
