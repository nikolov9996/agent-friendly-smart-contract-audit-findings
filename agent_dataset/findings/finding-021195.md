---
id: 21195
severity: "High"
---

# `AccountingManager::resetMiddle` will not behave as expected

## Description

The `resetMiddle` function in the `AccountingManager` contract is designed to reset the middle index of either the deposit or withdraw queue. This function is crucial for managing the order and processing of transactions within these queues, particularly in scenarios where recalculations are necessary to ensure fairness and accuracy in the distribution of shares or handling of withdrawals.

The function will work as expected when resetting the deposit queue, but it will not work for the reset of the withdrawal queue and will cause wrong withdrawal amount accounting to occurs.

To understand the issue we must first see how the withdrawal queue middle is calculated. The middle index of the withdrawal queue is updated during the process of calculating the withdrawal shares. This occurs in the `calculateWithdrawShares` function, which is designed to process queued withdrawal requests and assign the corresponding amount of base tokens to each request based on the current share price.

For each withdrawal request in the queue that has not yet been processed, the function calculates the amount of base tokens equivalent to the shares requested for withdrawal. After processing the maximum allowed iterations or reaching the end of the queue, the function updates the official middle index of the withdrawal queue to the last processed index (middleTemp) and increments the total base token amount needed for the current withdraw group `currentWithdrawGroup.totalCBAmount` (remember this state as it will be important).

Here is the relevant part of the code that handles the updating of the middle index:

```solidity
function calculateWithdrawShares(uint256 maxIterations) public onlyManager nonReentrant whenNotPaused {
    uint256 middleTemp = withdrawQueue.middle;
    uint64 i = 0;

    ...

    while (withdrawQueue.last > middleTemp && i < maxIterations) {
        WithdrawRequest storage data = withdrawQueue.queue[middleTemp];
        uint256 assets = previewRedeem(data.shares);
        data.amount = assets;
        data.calculationTime = block.timestamp;
        emit CalculateWithdraw(middleTemp, data.owner, data.receiver, data.shares, assets, block.timestamp);
        middleTemp += 1;
        i += 1;
    }
    currentWithdrawGroup.totalCBAmount += assetsNeededForWithdraw;
    withdrawQueue.middle = middleTemp;
}
```

Now let’s see how the `resetMiddle` function will cause an issue to occur in the withdrawal process:

```solidity
function resetMiddle(
    uint256 newMiddle,
    bool depositOrWithdraw
) public onlyManager {
    if (depositOrWithdraw) {
        emit ResetMiddle(newMiddle, depositQueue.middle, depositOrWithdraw);

        if (
            newMiddle > depositQueue.middle ||
            newMiddle < depositQueue.first
        ) {
            revert NoyaAccounting_INVALID_AMOUNT();
        }
        depositQueue.middle = newMiddle;
    } else {
        emit ResetMiddle(
            newMiddle,
            withdrawQueue.middle,
            depositOrWithdraw
        );

        if (
            newMiddle > withdrawQueue.middle ||
            newMiddle < withdrawQueue.first ||
            currentWithdrawGroup.isStarted
        ) {
            revert NoyaAccounting_INVALID_AMOUNT();
        }
        withdrawQueue.middle = newMiddle;
        //@audit currentWithdrawGroup.totalCBAmount is not reset
    }
}
```

As it can be seen the function doesn’t reset the value for current withdraw group `currentWithdrawGroup.totalCBAmount` which will keep its value from the previous calculation which is supposed to be wrong, and thus when later on the manager will call `calculateWithdrawShares` to calculate the withdrawal shares once again, `currentWithdrawGroup.totalCBAmount` will get incremented on the previously calculated amount which will result in a bigger base token amount needed for the withdrawal to be processed than what was supposed to be.

Thus the accounting for the current withdrawal group will be wrong. This issue will cause the following problems:

* First it will force the protocol manager to withdraw more funds than intended from the connectors to reach the amount needed for withdrawal of current group represented by `currentWithdrawGroup.totalCBAmount` (which is wrong -bigger- in our case after the reset has occurred), this will result in potential yield that could’ve been generated and thus a loss for funds for the protocol and its users.
* The worst that can happen is if `currentWithdrawGroup.totalCBAmount` after being incremented twice for the same group (the first time and the second time after the reset call as it wasn’t updated) is bigger that the current protocol TVL (which can happen especially in early days of the vault), in that case the protocol is unable to get necessary amount of funds to execute the withdrawal and the withdrawal process and funds will remain blocked until new deposit are made & executed.

## Proof of Concept

no poc

## Recommendation

To address this issue, the `reset` function must reset the withdrawal amount requested `currentWithdrawGroup.totalCBAmount` (set back to 0), the function should be modified as follows:

```solidity
function resetMiddle(
    uint256 newMiddle,
    bool depositOrWithdraw
) public onlyManager {
    if (depositOrWithdraw) {
        emit ResetMiddle(newMiddle, depositQueue.middle, depositOrWithdraw);

        if (
            newMiddle > depositQueue.middle ||
            newMiddle < depositQueue.first
        ) {
            revert NoyaAccounting_INVALID_AMOUNT();
        }
        depositQueue.middle = newMiddle;
    } else {
        emit ResetMiddle(
            newMiddle,
            withdrawQueue.middle,
            depositOrWithdraw
        );

        if (
            newMiddle > withdrawQueue.middle ||
            newMiddle < withdrawQueue.first ||
            currentWithdrawGroup.isStarted
        ) {
            revert NoyaAccounting_INVALID_AMOUNT();
        }
        withdrawQueue.middle = newMiddle;
        currentWithdrawGroup.totalCBAmount = 0;
    }
}
```

Fixed in commit 962d297e937e82d95e20739078a61b00eea47643.  
If we are resetting the withdrawal queue, we have to reset all withdrawals that are calculated so far. So we can safely set the `totalCBAmount` to 0.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the AccountingManager contract where the resetMiddle function is used to reposition the middle index of either the deposit or withdrawal queue. When the function is called for the withdrawal queue, it updates withdrawQueue.middle but fails to reset the accounting variable currentWithdrawGroup.totalCBAmount that tracks the total base token amount required for the current group of withdrawals. This omission creates a state inconsistency: after a reset, the next call to calculateWithdrawShares will add the newly calculated assetsNeededForWithdraw to the stale totalCBAmount value that still contains the amount from the previous calculation. Consequently the protocol believes it needs to withdraw more base tokens than actually required. The root cause is an incomplete reset of the withdrawal group state; the function checks bounds and the isStarted flag but does not clear the cumulative amount field. Exploitation is straightforward for any manager with permission to call resetMiddle: by resetting the middle index without resetting totalCBAmount, the manager can cause the accounting to double‑count the required withdrawal amount. When calculateWithdrawShares runs again, the inflated totalCBAmount leads the protocol to request excess funds from its connectors, reducing potential yield and, in extreme cases, exceeding the total value locked (TVL). If the inflated amount surpasses TVL, the vault cannot satisfy the withdrawal request and the user’s funds remain locked until new deposits arrive. The issue manifests under the condition that the manager invokes resetMiddle for the withdrawal queue while currentWithdrawGroup.isStarted is false and the new middle index lies within the allowed range. It affects the protocol’s financial integrity, the manager’s ability to correctly process withdrawals, and ultimately the users who expect to receive their funds. The bug was discovered during a formal audit by Code4rena, where the missing reset line was highlighted with an audit comment. It can be hard to notice because external balances and UI may still display correct values, while the internal accounting diverges, leading to unexpected larger withdrawal amounts or failed withdrawals that appear as “insufficient funds” errors. From a user’s perspective, a withdrawal may revert, return zero tokens, or remain pending indefinitely, contradicting the expectation that the request will be fulfilled promptly. The vulnerability belongs to the class of accounting state‑inconsistency bugs where a reset operation does not fully clear all related state variables. The proper remediation is to reset currentWithdrawGroup.totalCBAmount to zero when the withdrawal queue middle is reset, ensuring that subsequent share calculations start from a clean slate and that the protocol’s accounting matches the actual token flows.
