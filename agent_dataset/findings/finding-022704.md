---
id: 22704
severity: "High"
---

# Protocol unable to get extra Rewards in OCY_Convex_C.sol

## Description

Convex would wrap rewardToken for pools with IDs 151+, but the counting logic in OCY_Convex_C.sol makes it impossible for zivoe to forward yield. In OCY_Convex_C.sol, a convex pool with id 270 is used:

```solidity
/// @dev Convex information.
address public convexDeposit = 0xF403C135812408BFbE8713b5A23a04b3D48AAE31;
address public convexPoolToken = 0x383E6b4437b59fff47B619CBA855CA29342A8559;
address public convexRewards = 0xc583e81bB36A1F620A804D8AF642B63b0ceEb5c0;
uint256 public convexPoolID = 270;
```

In the following logic, rewardContract is defaulted to the address of extraRewards. This assumption is fine for pools with PoolId < 150, but would not work for IDs 151+.

```solidity
/// @notice Claims rewards and forward them to the OCT_YDL.
/// @param extra Flag for claiming extra rewards.
function claimRewards(bool extra) public nonReentrant {
IBaseRewardPool_OCY_Convex_C(convexRewards).getReward();
// Native Rewards (CRV, CVX)
uint256 rewardsCRV = IERC20(CRV).balanceOf(address(this));
uint256 rewardsCVX = IERC20(CVX).balanceOf(address(this));
if (rewardsCRV > 0) { IERC20(CRV).safeTransfer(OCT_YDL, rewardsCRV); }
if (rewardsCVX > 0) { IERC20(CVX).safeTransfer(OCT_YDL, rewardsCVX); }
// Extra Rewards
if (extra) {
uint256 extraRewardsLength =
IBaseRewardPool_OCY_Convex_C(convexRewards).extraRewardsLength();
for (uint256 i = 0; i < extraRewardsLength; i++) {
address rewardContract =
IBaseRewardPool_OCY_Convex_C(convexRewards).extraRewards(i);
uint256 rewardAmount = IBaseRewardPool_OCY_Convex_C(rewardContract).rewardToken().balanceOf(address(this));
if (rewardAmount > 0) { IERC20(rewardContract).safeTransfer(OCT_YDL, rewardAmount); }
}
}
}
```

According to convex doc, for pools with IDs 151+: VirtualBalanceRewardPool's rewardToken points to a wrapped version of the underlying token. This Token implementation can be found here: https://github.com/convex-eth/platform/blob/main/contracts/contracts/StashTokenWrapper.sol Just check convexRewards of pool 270: https://etherscan.io/address/0xc583e81bB36A1F620A804D8AF642B63b0ceEb5c0#readContract#F5 For index 0, it returns a VirtualBalanceRewardPool with rewardtoken = 0x85D81Ee851D36423A5784CD3Cb6f1a1193Cb5978. This contract is a StashTokenWrapper, which is consistent with what the convex documentation says. And, when IBaseRewardPool_OCY_Convex_C(convexRewards).getReward(); is triggered, reward tokens will be unwrapped and send to caller, so rewardAmount will always return 0, means such yield cannot be claimed for zivoe.

```solidity
address rewardContract =
IBaseRewardPool_OCY_Convex_C(convexRewards).extraRewards(i);
uint256 rewardAmount = IBaseRewardPool_OCY_Convex_C(rewardContract).rewardToken().balanceOf(address(this));
if (rewardAmount > 0) { IERC20(rewardContract).safeTransfer(OCT_YDL, rewardAmount); }
```

Users will lose extra rewards from convex pools with IDs 151+.

## Proof of Concept

no poc

## Recommendation

Change the logic above to:

```solidity
uint256 rewardAmount = IBaseRewardPool_OCY_Convex_C(rewardContract).rewardToken().token().balanceOf(address(this));
if (rewardAmount > 0) { IERC20(rewardContract).safeTransfer(OCT_YDL, rewardAmount); }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect assumption about the type of extra reward tokens returned by Convex pools with identifiers equal to or greater than 151. In the OCY_Convex_C contract the claimRewards function iterates over the list of extra rewards, treats each extraRewards(i) address as if it were a standard ERC‑20 token, and reads the balance of that address directly via rewardToken().balanceOf(this). For pools with IDs below 150 this works because the reward token is a plain ERC‑20 contract. However, for pools 151 and above Convex deploys a VirtualBalanceRewardPool whose rewardToken is a StashTokenWrapper – a wrapper contract that holds the real underlying token behind an additional .token() accessor. When getReward() is called, the wrapper automatically unwraps the underlying token and transfers it to the caller, but the wrapper’s own balance remains zero. Consequently the balance query performed by the OCY_Convex_C contract always returns zero, causing the extra reward amount to be considered absent and never forwarded to the OCT_YDL address. The bug therefore prevents the protocol from collecting any extra rewards from eligible Convex pools, leading to a loss of revenue for both the protocol and its users. The issue manifests only when the extra flag is true and the convexPoolID is 151 or higher; under those conditions the extraRewards loop executes but yields no transferable tokens. It was discovered during a manual audit when the reviewer compared the contract’s logic with Convex documentation and observed that the reward token address for pool 270 points to a StashTokenWrapper. The problem is subtle because the getReward() call does not revert and the contract’s balance for the wrapper token stays at zero, giving no obvious error signal. From a user’s perspective the UI may display that extra rewards are expected but the actual amount received is zero, violating the expectation that rewards earned in the pool are automatically forwarded. This class of bug can be described as a token‑wrapper handling error, where a contract fails to unwrap or correctly reference the underlying token before attempting a transfer. The correct remediation is to query the underlying token through the wrapper’s .token() function (e.g., rewardToken().token().balanceOf(this)) before performing the safeTransfer, ensuring that the actual reward balance is captured and forwarded.
