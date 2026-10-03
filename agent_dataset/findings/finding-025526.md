---
id: 25526
severity: "Low/Info"
---

# Consider using forceApprove instead of safeApprove in OstiumTraidingCallbacks

## Description

safeApprove should only be called when setting an initial allowance, because it reverts when a non-zero approval is changed to a non-zero approval.

Even though it's only called with either type(uint256).max or 0, using [forceApprove](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/141c947921cc5d23ee1d247c691a8b85cabbbd5d/contracts/token/ERC20/utils/SafeERC20.sol#L76>) is safer.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
