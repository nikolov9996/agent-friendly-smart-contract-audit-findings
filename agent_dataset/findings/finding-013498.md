---
id: 13498
severity: "High"
---

# Expanding reward token list right after linked YT expiration freezes the accumulated rewards

## Description

```solidity
function _getRewardTokens() internal view virtual override returns (address[] memory res) { //
<<
    return rewardTokens;
}
/// @notice allows anyone to add new rewardTokens to this SY if a new rewardToken is added to the Nitro pool
function updateRewardTokensList() public virtual {
    if (nitroPool == address(0)) return; // if nitroPool is not set, we don't need to update rewardTokens list
    address token1 = ICamelotNitroPool(nitroPool).rewardsToken1().token;
    address token2 = ICamelotNitroPool(nitroPool).rewardsToken2().token;
    if (token1 != address(0) && token1 != xGRAIL && !rewardTokens.contains(token1))
        rewardTokens.push(token1); // <<
    if (token2 != address(0) && token2 != xGRAIL && !rewardTokens.contains(token2))
        rewardTokens.push(token2); // <<
}
```
```solidity
function redeemDueInterestAndRewards(
    address user,
    bool redeemInterest,
    bool redeemRewards
) external nonReentrant updateData returns (uint256 interestOut, uint256[] memory rewardsOut) {
    if (!redeemInterest && !redeemRewards) revert Errors.YCNothingToRedeem();
    // if redeemRewards == true, this line must be here for obvious reason
    // if redeemInterest == true, this line must be here because of the reason above
    _updateAndDistributeRewards(user); // <<
}
```
```solidity
function _updateAndDistributeRewardsForTwo(address user1, address user2) internal virtual {
    (address[] memory tokens, uint256[] memory indexes) = _updateRewardIndex(); // <<
    if (tokens.length == 0) return;
    if (user1 != address(0) && user1 != address(this)) _distributeRewardsPrivate(user1, tokens, indexes); // <<
    if (user2 != address(0) && user2 != address(this)) _distributeRewardsPrivate(user2, tokens, indexes);
}
```
```solidity
function _updateRewardIndex() internal override returns (address[] memory tokens, uint256[] memory indexes) {
    tokens = getRewardTokens();
    if (isExpired()) {
        indexes = new uint256[](tokens.length);
        for (uint256 i = 0; i < tokens.length; i++) indexes[i] = postExpiry.firstRewardIndex[tokens[i]]; // <<
    } else {
        indexes = IStandardizedYield(SY).rewardIndexesCurrent();
    }
}
```
As index = postExpiry.firstRewardIndex[new_token] == 0, not being initialized, while userIndex will be set to INITIAL_REWARD_INDEX.Uint128() == 1, and deltaIndex = index - userIndex = 0 - 1:  
```solidity
function _distributeRewardsPrivate(address user, address[] memory tokens, uint256[] memory indexes) private {
    assert(user != address(0) && user != address(this));
    uint256 userShares = _rewardSharesUser(user);
    for (uint256 i = 0; i < tokens.length; ++i) {
        address token = tokens[i];
        uint256 index = indexes[i]; // <<
        uint256 userIndex = userReward[token][user].index;
        if (userIndex == 0) {
            userIndex = INITIAL_REWARD_INDEX.Uint128(); // <<
        }
        if (userIndex == index) continue;
        uint256 deltaIndex = index - userIndex; // <<
        uint256 rewardDelta = userShares.mulDown(deltaIndex);
        uint256 rewardAccrued = userReward[token][user].accrued + rewardDelta;
        userReward[token][user] = UserReward({index: index.Uint128(), accrued: rewardAccrued.Uint128()});
    }
}
```
```solidity
uint256 internal constant INITIAL_REWARD_INDEX = 1;
```
Impact: since rewardTokens list is append only and _setPostExpiryData() can't be run again, all the rewards within userRewardOwed balances will be permanently frozen in the YT contract.  
Likelihood: Low (SY with an expanding reward token list and not yet added reward token is a prerequisite) + Impact: Critical (most of the rewards are end up frozen) = Severity: High.

## Proof of Concept

no poc

## Recommendation

```solidity
function _distributeRewardsPrivate(address user, address[] memory tokens, uint256[] memory indexes) private {
    assert(user != address(0) && user != address(this));
    uint256 userShares = _rewardSharesUser(user);
    for (uint256 i = 0; i < tokens.length; ++i) {
        address token = tokens[i];
        uint256 index = indexes[i];
        uint256 userIndex = userReward[token][user].index;
        if (userIndex == 0) {
            userIndex = INITIAL_REWARD_INDEX.Uint128();
        }
        if (userIndex == index || index == 0) continue;
        uint256 deltaIndex = index - userIndex;
        uint256 rewardDelta = userShares.mulDown(deltaIndex);
        uint256 rewardAccrued = userReward[token][user].accrued + rewardDelta;
        userReward[token][user] = UserReward({index: index.Uint128(), accrued: rewardAccrued.Uint128()});
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the contract updates and distributes rewards after a yield token (YT) has expired. The contract maintains a list of reward tokens that can be expanded by calling updateRewardTokensList. When a new reward token is added after the YT expiration, the post‑expiry reward index for that token is never initialized and therefore remains zero. During reward distribution, the function _updateRewardIndex returns this zero index for the newly added token. The distribution routine then reads the user’s stored reward index, which is set to the constant INITIAL_REWARD_INDEX equal to one when the user has no prior record. Because the code calculates deltaIndex as index minus userIndex, the subtraction yields a negative value that underflows to a very large unsigned integer. The subsequent multiplication with the user’s share either produces an incorrect large number or, depending on the rounding function mulDown, results in zero reward delta. In either case the user’s accrued reward balance is never updated, effectively freezing any rewards associated with the newly added token. The rewardTokens array is append‑only and the post‑expiry data cannot be reset, so the frozen balances remain permanently locked in the contract. This situation can be triggered whenever (1) the standardized yield (SY) contract allows its reward token list to be expanded, (2) the YT has already reached its expiry, and (3) an external caller invokes updateRewardTokensList to add a new token. All users who hold the YT and are entitled to rewards for that token are affected; they will see their reward balance stay at zero despite having earned tokens, leading to a loss of expected payouts. The issue was discovered during a manual audit that examined the interaction between reward token list expansion and the post‑expiry reward index logic. It is subtle because the contract does not revert or emit an error; the reward distribution simply skips the new token without any visible warning, making the bug easy to miss in normal testing. To remediate, the distribution logic should either ignore tokens whose post‑expiry index is zero, initialize the index for newly added tokens, or prohibit adding reward tokens after the YT has expired. Any of these approaches would prevent the mismatch between userIndex and index and ensure that rewards remain claimable.
