---
id: 15054
severity: "High"
---

# AURA token will not be accounted for in `tokensIn`

## Description

When the controller sees a call to Aura's `getReward()` function, it uses the following logic to set `tokensOut` and `tokensIn`:
```solidity
function canCallGetReward(address target) internal view returns (bool, address[] memory, address[] memory) {
    uint256 rewardLength = IRewards(target).extraRewardsLength();
    address[] memory tokensIn = new address[](rewardLength + 1);
    for (uint256 i = 0; i < rewardLength; i++) {
        tokensIn[i] = IRewards(IRewards(target).extraRewards(i)).rewardToken();
    }
    tokensIn[rewardLength] = IRewards(target).rewardToken();
    return (true, tokensIn, new address[](0));
}
```
This sets the `tokensIn` to equal an array with all the `extraRewards` tokens, as well as the target contract's `rewardToken`.

However, if we examine the code itself, we will see that `getReward()` sends out all the tokens we accounted for (the `rewardToken` as well as all the `extraRewards`) and also makes the following call:
```solidity
IDeposit(operator).rewardClaimed(pid, _account, reward);
```
https://github.com/convex-eth/platform/blob/b93b7b77169777f3d508feffc646042709e40ef7/contracts/contracts/BaseRewardPool.sol#L263-L279

Following that logic, we find the following function in the `Booster.sol` contract:
```solidity
function rewardClaimed(uint256 pid, address address, uint256 _amount) external returns(bool){
    address rewardContract = poolInfo[_pid].crvRewards;

    //mint reward tokens
    ITokenMinter(minter).mint(address,amount);

    return true;
}
```
https://github.com/convex-eth/platform/blob/b93b7b77169777f3d508feffc646042709e40ef7/contracts/contracts/Booster.sol#L458C12-L466

As we can see, this additional call mints the `AURA` token to the `receiver`.

This token is not accounted for in `tokensIn`, which means it will not contribute to an account's balance in Sentiment. As a result, the account could be unfairly liquidated due to the missing balance.

## Proof of Concept

no poc

## Recommendation

Add the `AURA` token to the `tokensIn` array. If the deployment on Arbitrum matches Mainnet, it can be accessed as follows:
```solidity
IBooster(IRewards(target).operator()).minter();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an accounting mismatch in the reward‑claiming flow of the Aura/Convex reward pool. When the controller evaluates a call to the pool's getReward() function it builds a tokensIn array that contains the pool's primary reward token and any extra reward tokens returned by extraRewards(). This array is later used by the Sentiment accounting module to calculate a user’s collateral value and health factor. However, the getReward() implementation also invokes IDeposit(operator).rewardClaimed(pid, _account, reward), which forwards the claim to the Booster contract. Booster.rewardClaimed mints the AURA token directly to the user via the ITokenMinter(minter).mint call. Because the minted AURA token is created by a separate contract call and is not transferred through the pool, its address is never added to the tokensIn array. Consequently Sentiment does not recognise the newly minted AURA balance when computing the user’s total token holdings. The practical effect is that a user who successfully claims rewards receives AURA tokens that are invisible to the protocol’s risk engine; the user’s reported collateral may be lower than the actual value, potentially triggering an unjust liquidation or preventing a legitimate liquidation safeguard. This issue manifests whenever a user invokes getReward() on an Aura reward pool while the protocol relies on the tokensIn list for balance aggregation. It affects all participants whose positions are evaluated by Sentiment, including lenders, borrowers, and the protocol itself, because the hidden AURA tokens break the accounting assumptions that rewards increase collateral. The flaw was discovered during a manual audit of the reward‑claiming logic, where the auditor noticed that the token minted in rewardClaimed was not present in the tokensIn construction. The problem is subtle because the AURA token does not appear in any transfer event from the pool, making the missing balance easy to overlook in standard token‑flow analysis. To remediate the issue the tokensIn array should be extended to include the AURA token address, which can be obtained from the Booster contract via IBooster(IRewards(target).operator()).minter(). By accounting for the minted AURA token, Sentiment will correctly reflect the user’s full reward balance, preserving accurate health‑factor calculations and preventing unfair liquidations.
