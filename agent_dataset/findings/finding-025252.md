---
id: 25252
severity: "Low/Info"
---

# Withdraw requests could be stored in a simpler way in glAVAX

## Description

Global and user withdrawal requests are stored in a mapping and a variable tracking the length respectively. Thus, it's easier to use 1 array of global withdraw requests and a mapping with an array for each user with their individual withdraw requests, pointing to the global array of withdraw requests.

The functions that would be affected by this change are _withdrawRequest(), _claim(), _cancel(), claim(), claimAll(), cancelAll() and cancel().

## Proof of Concept

No PoC provided.

## Recommendation

When creating a new withdraw request in _withdrawRequest(), do

```solidity
uint256 globalWithdrawRequestId = withdrawRequests.push(request) - 1;
userWithdrawRequests.push(globalWithdrawRequestId);
```

When claiming or cancelling individually, do

```solidity
uint256 globalId = withdrawRequests[user][id]
uint256 lastUserRequest = withdrawRequests[user].length - 1;
if (lastUserRequest != 0) withdrawRequests[user][id] = withdrawRequests[user][lastUserRequest];
withdrawRequests[user].pop();
withdrawRequest = withdrawRequests[globalId];
... delete withdrawRequests[globalId];
```

Note that on claimAll() and cancelAll(), looping through the method above could cause issues because it changes the position of the current index with the last index in each iteration.

In that case, it would make more sense to 1. cache the length of the array 2. loop through the array, starting at the last index 3. pop the element at the end of the body of the loop
