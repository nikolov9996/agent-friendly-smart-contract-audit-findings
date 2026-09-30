---
id: 7154
severity: "High"
---

# Attacker could steal almost all the bonus tokens in BathBuddy Vesting Wallet

## Description

```solidity
BathBuddy is a Vesting Wallet that payout withdrawers any `bonusTokens` they may have accrued while staking in the Bath Token (e.g. network incentives/governance tokens).

BathBuddy Vesting Wallet releases a user their relative share of the pool’s total vested bonus token during the withdraw call on BathToken.sol. This vesting occurs linearly over Unix time.

It was observed that an attacker could steal almost all the `bonusTokens` in the BathBuddy Vesting Wallet.
```

## Proof of Concept

```solidity
The root cause of this issue is that the amount of `bonusTokens` that a user is entitled to is based on their relative share of the pool’s total vested bonus token at the point of the withdraw call. It is calculated based on the user’s “spot” share in the pool.

Thus, it is possible for an attacker to deposit large amount of tokens into a BathToken Pool to gain significant share of the pool (e.g. 95%), and then withdraw the all the shares immediately. The withdraw call will trigger the `BathToken.distributeBonusTokenRewards`, and since attacker holds overwhelming amount of share in the pool, they will receive almost all the `bonusToken` in the BathBuddy Vesting wallet, leaving behind dust amount of `bonusToken` in the wallet. This could be perform in an atomic transaction and attacker can leverage on flash-loan to fund this attack.

The following shows an example of this issue:

  1. A sponsor sent 1000 DAI to the BathBuddy Vesting Wallet to be used as `bonusTokens` for bathWETH pool. The vesting duration is 4 weeks.
  2. Alice and Bob deposited 50 WETH and 50 WETH respectively. The total underlying asset of bathWETH is 100 WETH after depositing. Each of them hold 50% of the shares in the pool.
  3. Fast forward to the last hour of the vesting period, most of the `bonusToken` have been vested and ready for the recipients to claim. In this example, estimate 998 DAI are ready to be claimed at the final hour.
  4. Since Alice has 50% stake in the pool, she should have accured close to 449 DAI at this point. If she decided to withdraw all her bathWETH LP tokens at this point, she would receive close to 449 DAI as `bonusTokens`. But she choose not to withdraw yet.
  5. Unfortunately, an attacker performed a flash-loan to borrow 8500 WETH, and deposit large amount of WETH into the bathWETH gain significant share of the pool, and then withdraw the all the shares immediately.
  6. Since attacker hold the an overwhelming amount of shares in the pool, they will receive almost all the `bonusToken` (around 997 DAI) in the BathBuddy Vesting wallet, leaving behind dust amount of `bonusToken` in the wallet.
  7. At this point, Alice decided to withdraw all her bathWETH LP token. She only received dust amount of 0.7 DAI as `bonusTokens`

The following code shows that the amount of `bonusTokens` a user is entitled is based on the user’s current share in the pool - `amount = releasable * sharesWithdrawn/initialTotalSupply`.

/// @inheritdoc IBathBuddy
/// @dev Added and modified release function. Should be the only callable release function
function release(
    IERC20 token,
    address recipient,
    uint256 sharesWithdrawn,
    uint256 initialTotalSupply,
    uint256 poolFee
) external override {
    require(
        msg.sender == beneficiary,
        "Caller is not the Bath Token beneficiary of these rewards"
    );
    uint256 releasable = vestedAmount(
        address(token),
        uint64(block.timestamp)
    ) - released(address(token));
    if (releasable > 0) {
        uint256 amount = releasable.mul(sharesWithdrawn).div(
            initialTotalSupply
        );
        uint256 _fee = amount.mul(poolFee).div(10000);

        ..SNIP..

        uint256 amountWithdrawn = amount.sub(_fee);
        token.transfer(recipient, amountWithdrawn);

        _erc20Released[address(token)] += amount;
        ..SNIP..
    }
}

Following is the test output that demonstrates the above scenario:

  Contract: Rubicon Exchange and Pools Original Tests
    Deployment
      ✓ is deployed (1783ms)
    Bath House Initialization of Bath Pair and Bath Tokens
      ✓ Bath House is deployed and initialized (66ms)
        new bathWETH! 0x237eda6f0102c1684caEbA3Ebd89e26a79258C6f
      ✓ WETH Bath Token for WETH asset is deployed and initialized (131ms)
      ✓ Init BathBuddy Vesting Wallet and Add BathBuddy to WETH BathToken Pool (54ms)
      ✓ Bath Pair is deployed and initialized w/ BathHouse (59ms)
        undefined
      ✓ Alice deposit 50 WETH to WETH bathTokens (137ms)
        undefined
      ✓ Bob deposit 50 WETH to WETH bathTokens (174ms)
bathAssetInstance.bonusTokens.length = 1
bathBuddyInstance (Vesting Wallet) has 1000 DAI
bathBuddyInstance.vestedAmount(DAI) = 0.000413359788359788
bathBuddyInstance.vestedAmount(DAI) = 500.000413359788359788 (End of 2nd week)
bathBuddyInstance.vestedAmount(DAI) = 998.512318121693121693 (Last hour of the vesting period)
0 DAI has been released from BathBuddy Vesting Wallet
Charles has 8500 bathWETH token, 0 DAI, 0 WETH
Charles withdraw all his bathWETH tokens
997.338978147402060445 DAI has been released from BathBuddy Vesting Wallet
Charles has 0 bathWETH token, 997.039776453957839827 DAI, 8497.45 WETH
Alice has 5 bathWETH token, 0 DAI, 0 WETH
998.075233164534207763 DAI has been released from BathBuddy Vesting Wallet
Alice has 0 bathWETH token, 0.736034140627007674 DAI, 6.2731175 WETH
      ✓ Add Rewards (100 DAI) to BathBuddy Vesting Wallet  (749ms)
bathAssetInstance: underlyingBalance() = 6.2768825 WETH, balanceOf = 6.2768825 WETH, Outstanding Amount = 0 WETH
      ✓ [Debug]

Attacker Charles deposited 8500 WETH to the pool and withdraw them immediately at the final hour, and obtained almost all of the `bonusTokens` (997 DAI). When Alice withdraw from the pool, she only received 0.7 DAI as `bonusTokens`.

Script can be found <https://gist.github.com/xiaoming9090/2252f6b6f7e62fca20ecfbaac6f754f5>

Note: Due to some unknown issue with the testing environment, please create a new `BathBuddy.released2` functions to fetch the amount of token already released.
```

## Recommendation

```solidity
Update the reward mechanism to ensure that the `bonusTokens` are distribute fairly and rewards of each user are accured correctly.

In the above example, since Alice holds 50% of the shares in the pool throughout the majority of the reward period, she should be entitled to close to 50% to the rewards/bonus. Anyone who joins the pool at the last hour of the reward period should only be entitled to dust amount of `bonusToken`.

Additionally, “spot” (or current) share of the pool should not be used to determine the amount of `bonusToken` a user is entitled to as it is vulnerable to pool/share manipulation or flash-loan attack. Checkpointing mechanism should be implemented so that at the minimum, the user’s amount of share in the previous block is used for determining the rewards. This make flash-loan attack infeasible as such attack has to happen within the same block/transaction.

For distributing bonus/rewards, I would suggest checking out a widely referenced [Synthetix’s Reward](https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol) Contract as I think that it would be more relevant than OZ’s Vesting Wallet for this particular purpose.

Great writeup and POC from the warden! [#71](https://github.com/code-423n4/2022-05-rubicon-findings/issues/71) is a little similar, but instead of a flash loan, uses a different method of repeated deposits and withdrawals to achieve the same result.

Because of the higher quality of this report, I’m using it as the primary issue.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the BathBuddy Vesting Wallet calculates a user’s entitlement to bonus tokens. The contract determines the reward amount at the moment of withdrawal by multiplying the total releasable bonus tokens by the caller’s current (spot) share of the pool and dividing by the initial total supply of shares. Because the calculation uses the instantaneous share balance rather than a historically‑locked snapshot, an attacker can temporarily acquire an overwhelming proportion of the pool, claim the reward, and then relinquish that position in the same transaction. In practice, an adversary can perform a flash‑loan to borrow a large amount of the underlying asset, deposit it into the BathToken pool just before the vesting period ends, and immediately withdraw both the deposited liquidity and the associated bonus tokens. The withdraw call triggers the reward distribution, and the attacker’s inflated share causes the contract to allocate almost the entire remaining bonus token balance to them, leaving only a negligible dust amount for legitimate participants. This attack can be executed atomically, meaning the pool’s share distribution is manipulated within a single block, making the exploit difficult to detect during normal operation. The impact is severe: honest users who later withdraw receive dramatically reduced bonuses, effectively losing the majority of the incentive rewards that were intended for them. The issue affects all participants of the BathBuddy vesting scheme, including token holders, liquidity providers, and the protocol’s economic model, as it undermines the fairness and accounting assumptions underlying the reward system. The flaw was discovered during a security audit and reproduced in a test suite that demonstrated an attacker draining roughly 997 DAI of a 1000 DAI bonus pool while legitimate users received less than one DAI. The problem is subtle because the contract’s code appears to correctly compute a proportional share, yet it fails to account for the temporal dimension of share ownership. The recommended mitigation is to replace the spot‑share calculation with a checkpointing mechanism that records each user’s share balance at the end of the previous block (or at the start of the vesting interval) before rewards are allocated, thereby preventing flash‑loan manipulation and ensuring rewards are distributed according to the actual historical stake. Implementing a reward distribution pattern similar to Synthetix’s StakingRewards contract, which accrues rewards over time per share, would resolve the issue and restore the intended economic fairness.
