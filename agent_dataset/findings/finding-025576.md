---
id: 25576
severity: "Crit/High"
---

# DOS of completeQueuedWithdrawal when ERC20 buffer is filled

## Description



## Proof of Concept

## Issue Description

When the `OperatorDelegator::completeQueuedWithdrawal` function is invoked to finalize a withdrawal from EL, it attempts to utilize the accumulated ERC20 tokens to fill the ERC20 withdrawal buffer, as demonstrated in the code snippet below:

```solidity
function completeQueuedWithdrawal(
    IDelegationManager.Withdrawal calldata withdrawal,
    IERC20[] calldata tokens,
    uint256 middlewareTimesIndex
) external nonReentrant onlyNativeEthRestakeAdmin {
    uint256 gasBefore = gasleft();
    if (tokens.length != withdrawal.strategies.length) revert MismatchedArrayLengths();

    // Complete the queued withdrawal from EigenLayer with receiveAsToken set to true
    delegationManager.completeQueuedWithdrawal(withdrawal, tokens, middlewareTimesIndex, true);

    IWithdrawQueue withdrawQueue = restakeManager.depositQueue().withdrawQueue();
    for (uint256 i; i < tokens.length; ) {
        if (address(tokens[i]) == address(0)) revert InvalidZeroInput();

        // Deduct queued shares for tracking TVL
        queuedShares[address(tokens[i])] -= withdrawal.shares[i];

        // Check if the token is not Native ETH
        if (address(tokens[i]) != IS_NATIVE) {
            // Check the withdrawal buffer and fill if below buffer target
            uint256 bufferToFill = withdrawQueue.getBufferDeficit(address(tokens[i]));

            // Get the balance of this contract
            uint256 balanceOfToken = tokens[i].balanceOf(address(this));
            if (bufferToFill > 0) {
                bufferToFill = (balanceOfToken <= bufferToFill) ? balanceOfToken : bufferToFill;

                // Update the amount to send to the operator Delegator
                balanceOfToken -= bufferToFill;

                // Safely approve for depositQueue
                tokens[i].safeApprove(address(restakeManager.depositQueue()), bufferToFill);

                // Fill the Withdraw Buffer via depositQueue
                restakeManager.depositQueue().fillERC20withdrawBuffer(
                    address(tokens[i]),
                    bufferToFill
                );
            }

            // Deposit remaining tokens back to EigenLayer
            if (balanceOfToken > 0) {
                _deposit(tokens[i], balanceOfToken);
            }
        }
        unchecked {
            ++i;
        }
    }

    // Emit the Withdraw Completed event with withdrawalRoot
    emit WithdrawCompleted(
        delegationManager.calculateWithdrawalRoot(withdrawal),
        withdrawal.strategies,
        withdrawal.shares
    );
    // Record the current spent gas
    _recordGas(gasBefore);
}
```

The function iterates over the withdrawn tokens array and, for each token, checks if the withdrawal buffer needs filling. If required, the function attempts to call the `depositQueue::fillERC20withdrawBuffer` function, which is responsible for directing the ERC20 to the withdrawal queue contract to fill the buffer.

The issue arises because the `depositQueue::fillERC20withdrawBuffer` function can only be accessed by the `RestakeManager` contract, as it enforces the `onlyRestakeManager` modifier, as depicted below:

```solidity
/// @dev Allows only the RestakeManager address to call functions
modifier onlyRestakeManager() {
    if (msg.sender != address(restakeManager)) revert NotRestakeManager();
    _;
}

function fillERC20withdrawBuffer(
    address _asset,
    uint256 _amount
) external nonReentrant onlyRestakeManager {
    ...
}
```

Consequently, when the `completeQueuedWithdrawal` function attempts this call, it reverts because `OperatorDelegator` lacks access to the `depositQueue::fillERC20withdrawBuffer` function. This results in the entire withdrawal completion call reverting, rendering it impossible for the admin to retrieve funds from EL.

In summary, this issue triggers a persistent DOS of the `OperatorDelegator::completeQueuedWithdrawal` function, preventing the protocol and users from withdrawing funds from EL and resulting in a loss of funds.

## Impact

Persistent DOS of the `OperatorDelegator::completeQueuedWithdrawal` function, preventing the protocol from withdrawing funds from EL and leading to fund losses for the protocol and users.

## Recommendation

The simplest resolution is to grant access to the `depositQueue::fillERC20withdrawBuffer` function to everyone by removing the `onlyRestakeManager` modifier. This adjustment introduces no vulnerabilities to the protocol since any user calling it effectively donates funds to the protocol (to the withdrawal queue).
