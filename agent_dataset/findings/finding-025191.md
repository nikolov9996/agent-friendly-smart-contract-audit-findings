---
id: 25191
severity: "Medium"
---

# BaseFlasher transfers tokens and then calls xBundle(...), so the sent tokens can't be returned due to the balance check

## Description

The BaseRouter checks if the balances of the assets remain the same after the xBundle(...) execution. The BaseFlasher, _requestorExecution(...) is implemented in the following way

```solidity
IERC20(asset).safeTransfer(requestor, amount);
requestor.functionCall(requestorCalldata);
// approve flashloan source address to spend to repay flashloan
IERC20(asset).safeApprove(getFlashloanSourceAddr(asset), amount + fee);
```

Thus, when xBundle(...) is called in requestor.functionCall(requestorCalldata);, the initial balance of the BaseRouter will take into account the received funds from the flashloan, such that it will be impossible to return the funds at the end of the call.

## Proof of Concept

[https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCCantUseFlashloanFunds.t.sol#L97](<https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/POCCantUseFlashloanFunds.t.sol#L97>)

## Recommendation

Similarly to xReceive(...) of the ConnextRouter, the BaseRouter could implement a similar function. In this case, the caller of, let's say, flashloanReceive(...), could be whitelisted to one of the flashers.
