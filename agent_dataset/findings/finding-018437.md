---
id: 18437
severity: "High"
---

# Reward accounting is incorrect in `BathBuddy` contract

## Description

The `BathBuddy` contracts implements rewards for liquidity providers (holders of `BathToken`). The contract is modeled after the famous Synthetix staking contract, with some tweaks to support rewards for multiple tokens at the same time.

The implementation overall is correct; however, there is a critical difference with the Synthetix contract that is ignored in the `BathBuddy` contract. In the Synthetix implementation, the main actions related to rewards accounting are the `stake` and `withdraw` actions. These trigger the `updateReward` modifier to ensure correct reward accounting. Staked tokens cannot be transferred, as these are held in the staking contract. In the `BathBuddy` implementation, things are very different as there is no staking. Rewards are intended to be distributed directly to holders of the `BathToken` without any need of staking the tokens in the contract. This means that, as there is no “staking” action in the `BathBuddy` implementation (i.e. depositing funds in the contract), rewards fail to be correctly accounted whenever `BathToken` are minted, burned or transferred between different accounts.

These are two critical places in the code where the `BathBuddy` contract uses the state from the `BathToken`, but fails to be triggered whenever the state in the `BathToken` is modified. The first is `rewardPerToken`, which calculates the amount of rewards that should correspond to one unit of the `BathToken` token. This is logically dependent on the total supply of the token (lines 124 and 133):

```solidity
    function rewardPerToken(address token) public view returns (uint256) {
        require(friendshipStarted, "I have not started a bathToken friendship");

        if (IERC20(myBathTokenBuddy).totalSupply() == 0) {
            return rewardsPerTokensStored[token];
        }
        return
            rewardsPerTokensStored[token].add(
                lastTimeRewardApplicable(token)
                    .sub(lastUpdateTime[token])
                    .mul(rewardRates[token])
                    .mul(1e18)
                    .div(IERC20(myBathTokenBuddy).totalSupply())
            );
    }
```

The other place is in the `earned` function which uses the `BathToken` `balanceOf` function of an account (lines 146-147):

```solidity
    function earned(
        address account,
        address token
    ) public view override returns (uint256) {
        require(friendshipStarted, "I have not started a bathToken friendship");

        return
            IERC20(myBathTokenBuddy) // Care with this?
                .balanceOf(account)
                .mul(
                    rewardPerToken(token).sub(
                        userRewardsPerTokenPaid[token][account]
                    )
                )
                .div(1e18)
                .add(tokenRewards[token][account]);
    }

    function getRewardForDuration(
        address token
    ) external view returns (uint256) {
        return rewardRates[token].mul(rewardsDuration[token]);
    }
```

Since the whole `BathBuddy` contract is dependent on the total supply and account balance state of the paired `BathToken` contract, the following actions in the token should update the rewards state in `BathBuddy`:

  * `mint` and `burn`, as these modify the total supply of the token and the balances of the account whose tokens are minted or burned.
  * `transfer` and `transferFrom`, as these modify the balances of the sender and recipient accounts.

As the `BathBuddy` `updateReward` modifier fails to be triggered when the mentioned state in the `BathToken` is modified, reward accounting will be incorrect for many different scenarios. We’ll explore one of these in the next section.

## Proof of Concept

In the following test, we demonstrate one of the possible scenarios where reward accounting is broken. This is a simple case in which rewards fail to be updated when a token transfer is executed. Alice has 1e18 `BathTokens`, at the middle of the rewards duration period she sends all her tokens to Bob. The expected outcome should be that Alice would earn half of the rewards, as she held the tokens for the half of the duration period. But when the duration period has ended, we call `getReward` for both Alice and Bob and we can see that Alice got nothing and Bob earned 100% of the rewards.

_Note: the snippet shows only the relevant code for the test. Full test file can be found[here](https://gist.github.com/romeroadrian/f3b7d6f9ab043340de7deb67a9c515e5)._

```solidity
    function test_BathBuddy_IncorrectRewardAccounting() public {
        // Setup rewards
        uint256 startTime = block.timestamp;
        uint256 duration = 10_000 seconds;
        vm.prank(bathBuddyOwner);
        bathBuddy.setRewardsDuration(duration, address(rewardToken));

        uint256 rewardAmount = 100 ether;
        rewardToken.mint(address(bathBuddy), rewardAmount);
        vm.prank(bathBuddyOwner);
        bathBuddy.notifyRewardAmount(rewardAmount, rewardToken);

        // Mint bathTokens to Alice
        uint256 bathTokenAmount = 1 ether;
        bathToken.mint(alice, bathTokenAmount);

        // Simulate half of the duration time passes
        vm.warp(startTime + duration / 2);

        // Alice transfers tokens for Bob at middle of the period
        vm.prank(alice);
        bathToken.transfer(bob, bathTokenAmount);

        // Simulate complete duration time passes
        vm.warp(startTime + duration);

        // Trigger getRewards for Alice
        vm.prank(bathBuddyHouse);
        bathBuddy.getReward(rewardToken, alice);

        // Trigger getRewards for Bob
        vm.prank(bathBuddyHouse);
        bathBuddy.getReward(rewardToken, bob);

        // Alice gets nothings and Bob gets the full rewards, even though Alice held the tokens for half the duration time
        assertEq(rewardToken.balanceOf(alice), 0);
        assertEq(rewardToken.balanceOf(bob), rewardAmount);
    }
```

## Recommendation

There are two recommended paths here. The easy path would be to just add the `stake` and `withdraw` functions to the `BathBuddy` contract similar to how the original `StakingRewards` contract works on Synthetix. However, this may change the original intention of the protocol as rewards won’t be earned just by holding `BathTokens`, they will need to be staked (rewards will only be distributed to stakers).

The other path, and a bit more complex, would be to modify the `BathToken` contract (the `cToken`) so that burn, mint and transfer actions trigger the update on the paired `BathBuddy` contract.

This write-up encapsulates the issues arising from forking the staking contract, but doing away with the staking portion through the usage of `balanceOf()` and `totalSupply()`.

  * No initialisation of `userRewardsPerTokenPaid`
  * Doesn’t account for holding duration 

I think that in the duplicate, two categories of issues have been merged into one.

So the two separate problems that have been merged into one are:

  1. Difference of implementation from synthetix, where there is no modifier on stake and withdraw. Hence, the calculation is flawed, leading to being able to claim the reward for whole duration by minting at the last moment, reducing others’ rewards.
  2. Second, is the ability to transfer the token and claim (again and again, etc) until the contract is drained.

Both are different issues and require different solutions.

Just for example, two marked duplicates are: [#1074](https://github.com/code-423n4/2023-04-rubicon-findings/issues/1074) and [#1168](https://github.com/code-423n4/2023-04-rubicon-findings/issues/1168). Each explain separate issues of uneven distribution and draining.

(2) is enabled by (1). 

The removal of staking & withdrawing (1) also led to the removal of initialisation of the `rewardsPerToken`, which allows you to do (2).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The BathBuddy contract distributes reward tokens to holders of the BathToken, but it relies on the total supply and individual balances of BathToken to compute rewardPerToken and earned values. In the original Synthetix staking model, reward accounting is updated only during explicit stake and withdraw actions, which invoke an updateReward modifier. BathBuddy removed staking entirely and expects rewards to accrue automatically for any token holder. Because there is no mechanism that triggers the updateReward modifier when the BathToken state changes – specifically when tokens are minted, burned, transferred, or transferred via transferFrom – the internal accounting variables (rewardsPerTokensStored, userRewardsPerTokenPaid, tokenRewards) are not refreshed. Consequently, the rewardPerToken calculation uses a stale totalSupply value and the earned function multiplies a stale balance, leading to incorrect reward amounts. An attacker can exploit this by transferring all tokens to another address at the midpoint of the reward period; the sender’s earned balance remains unchanged (often zero) while the recipient’s balance is multiplied by the full reward amount, effectively stealing the entire reward pool. The impact is that legitimate users may receive no rewards despite holding tokens for part of the distribution window, while a malicious user can drain the reward contract. This condition occurs whenever BathToken’s supply or balances change without a corresponding call to BathBuddy’s updateReward logic – i.e., on any mint, burn, transfer, or transferFrom operation. All token holders and the protocol’s reward distribution mechanism are affected because the accounting invariant that rewards are proportional to time‑weighted holdings is broken. The issue was discovered during a functional test that simulated a half‑duration transfer and observed that the original holder received zero reward while the receiver obtained the full amount. The bug is subtle because the contract compiles and appears to follow the Synthetix formula, yet the missing hooks mean the state is never synchronized with token movements, making the error easy to miss in code review. To remediate, the contract must either re‑introduce explicit stake/withdraw functions that invoke updateReward, or the BathToken contract must be extended so that mint, burn, and transfer operations emit a callback or invoke a function on BathBuddy to update rewards before the token state changes. In either case, the reward accounting must be tied to every change in totalSupply or balance to preserve the intended proportional distribution of rewards.
