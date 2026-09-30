---
id: 17091
severity: "High"
---

# fee loss in AutoPxGmx and AutoPxGlp and reward loss in AutoPxGlp by calling `PirexRewards.claim

## Description

Function `compound()` in `AutoPxGmx` and `AutoPxGlp` contracts is for compounding `pxGLP` (and additionally `pxGMX`) rewards. it works by calling `PirexGmx.claim(px*, this)` to collect the rewards of the vault and then swap the received amount (to calculate the reward, contract save the balance of a contract in that reward token before and after the call to the `claim()` and by subtracting them finds the received reward amount) and deposit them in `PirexGmx` again for compounding and in doing so it calculates fee based on what it received and in `AutoPxGlp` case it calculates `pxGMX` rewards too based on the extra amount contract receives during the execution of `claim()`. But attacker can call `PirexGmx.claim(px*, PirexGlp)` directly and make `PirexGmx` contract to transfer (`gmxBaseReward` and `pxGmx`) rewards to `AutoPxGlp` and in this case the logics of fee calculation and reward calculation in `compound()` function won’t get executed and contract won’t get it’s fee from rewards and users won’t get their `pxGmx` reward. So this bug would cause fee loss in `AutoPxGmx` and `AutoPxGlp` for contract and `pxGmx`’s reward loss for users in `AutoPxGlp`.

## Proof of Concept

The bug in `AutoPxGmx` is similar to `AutoPxGlp`, so we only give Proof of Concept for `AutoPxGlp`.

This is `compound()` function code in `AutoPxGlp` contract:

```solidity
function compound(
    uint256 minUsdg,
    uint256 minGlp,
    bool optOutIncentive
)
    public
    returns (
        uint256 gmxBaseRewardAmountIn,
        uint256 pxGmxAmountOut,
        uint256 pxGlpAmountOut,
        uint256 totalPxGlpFee,
        uint256 totalPxGmxFee,
        uint256 pxGlpIncentive,
        uint256 pxGmxIncentive
    )
{
    if (minUsdg == 0) revert InvalidParam();
    if (minGlp == 0) revert InvalidParam();

    uint256 preClaimTotalAssets = asset.balanceOf(address(this));
    uint256 preClaimPxGmxAmount = pxGmx.balanceOf(address(this));

    PirexRewards(rewardsModule).claim(asset, address(this));
    PirexRewards(rewardsModule).claim(pxGmx, address(this));

    // Track the amount of rewards received
    gmxBaseRewardAmountIn = gmxBaseReward.balanceOf(address(this));

    if (gmxBaseRewardAmountIn != 0) {
        // Deposit received rewards for pxGLP
        (, pxGlpAmountOut, ) = PirexGmx(platform).depositGlp(
            address(gmxBaseReward),
            gmxBaseRewardAmountIn,
            minUsdg,
            minGlp,
            address(this)
        );
    }

    // Distribute fees if the amount of vault assets increased
    uint256 newAssets = totalAssets() - preClaimTotalAssets;
    if (newAssets != 0) {
        totalPxGlpFee = (newAssets * platformFee) / FEE_DENOMINATOR;
        pxGlpIncentive = optOutIncentive
            ? 0
            : (totalPxGlpFee * compoundIncentive) / FEE_DENOMINATOR;

        if (pxGlpIncentive != 0)
            asset.safeTransfer(msg.sender, pxGlpIncentive);

        asset.safeTransfer(owner, totalPxGlpFee - pxGlpIncentive);
    }

    // Track the amount of pxGMX received
    pxGmxAmountOut = pxGmx.balanceOf(address(this)) - preClaimPxGmxAmount;

    if (pxGmxAmountOut != 0) {
        // Calculate and distribute pxGMX fees if the amount of pxGMX increased
        totalPxGmxFee = (pxGmxAmountOut * platformFee) / FEE_DENOMINATOR;
        pxGmxIncentive = optOutIncentive
            ? 0
            : (totalPxGmxFee * compoundIncentive) / FEE_DENOMINATOR;

        if (pxGmxIncentive != 0)
            pxGmx.safeTransfer(msg.sender, pxGmxIncentive);

        pxGmx.safeTransfer(owner, totalPxGmxFee - pxGmxIncentive);

        // Update the pxGmx reward accrual
        _harvest(pxGmxAmountOut - totalPxGmxFee);
    } else {
        // Required to keep the globalState up-to-date
        _globalAccrue();
    }

    emit Compounded(
        msg.sender,
        minGlp,
        gmxBaseRewardAmountIn,
        pxGmxAmountOut,
        pxGlpAmountOut,
        totalPxGlpFee,
        totalPxGmxFee,
        pxGlpIncentive,
        pxGmxIncentive
    );
}
```

As you can see contract collects rewards by calling `PirexRewards.claim()` and in the line `uint256 newAssets = totalAssets() - preClaimTotalAssets;` contract calculates the received amount of rewards (by subtracting the balance after and before reward claim) and then calculates fee based on this amount `totalPxGlpFee = (newAssets * platformFee) / FEE_DENOMINATOR;` and then sends the fee in the line `asset.safeTransfer(owner, totalPxGlpFee - pxGlpIncentive)` for `owner`. 

The logic for `pxGmx` rewards are the same. As you can see the calculation of the fee is based on the rewards received, and there is no other logic in the contract to calculate and transfer the fee of protocol. So if `AutoPxGpl` receives rewards without `compound()` getting called then for those rewards fee won’t be calculated and transferred and protocol would lose it’s fee.

In the line `_harvest(pxGmxAmountOut - totalPxGmxFee)` contract calls `_harvest()` function to update the `pxGmx` reward accrual and there is no call to `_harvest()` in any other place and this is the only place where `pxGmx` reward accrual gets updated. The contract uses `pxGmxAmountOut` which is the amount of `gmx` contract received during the call (code calculates it by subtracting the balance after and before reward claim: `pxGmxAmountOut = pxGmx.balanceOf(address(this)) - preClaimPxGmxAmount;`) so contract only handles accrual rewards in this function call and if some `pxGmx` rewards claimed for contract without `compund()` logic execution then those rewards won’t be used in `_harvest()` and `_globalAccrue()` calculation and users won’t receive those rewards.

As mentioned attacker can call `PirexRewards.claim(pxGmx, AutoPxGpl)` directly and make `PirexRewads` contract to transfer `AutoPxGpl` rewards. This is `claim()` code in `PirexRewards`:

```solidity
function claim(ERC20 producerToken, address user) external {
    if (address(producerToken) == address(0)) revert ZeroAddress();
    if (user == address(0)) revert ZeroAddress();

    harvest();
    userAccrue(producerToken, user);

    ProducerToken storage p = producerTokens[producerToken];
    uint256 globalRewards = p.globalState.rewards;
    uint256 userRewards = p.userStates[user].rewards;

    // Claim should be skipped and not reverted on zero global/user reward
    if (globalRewards != 0 && userRewards != 0) {
        ERC20[] memory rewardTokens = p.rewardTokens;
        uint256 rLen = rewardTokens.length;

        // Update global and user reward states to reflect the claim
        p.globalState.rewards = globalRewards - userRewards;
        p.userStates[user].rewards = 0;

        emit Claim(producerToken, user);

        // Transfer the proportionate reward token amounts to the recipient
        for (uint256 i; i < rLen; ++i) {
            ERC20 rewardToken = rewardTokens[i];
            address rewardRecipient = p.rewardRecipients[user][rewardToken];
            address recipient = rewardRecipient != address(0)
                ? rewardRecipient
                : user;
            uint256 rewardState = p.rewardStates[rewardToken];
            uint256 amount = (rewardState * userRewards) / globalRewards;

            if (amount != 0) {
                // Update reward state (i.e. amount) to reflect reward tokens transferred out
                p.rewardStates[rewardToken] = rewardState - amount;

                producer.claimUserReward(
                    address(rewardToken),
                    amount,
                    recipient
                );
            }
        }
    }
}
```

As you can see it can be called by anyone for any user. So to perform this attack, attacker would perform these steps:

  1. Suppose `AutoPxGpl` has pending rewards, for example 100 `pxGmx` and 100 `weth`.
  2. Attacker would call `PirexRewards.claim(pxGmx, AutoPxGpl)` and `PirexRewards.claim(pxGpl, AutoPxGpl)` and `PirexRewards` contract would calculate and claim and transfer `pxGmx` rewards and `weth` rewards of `AutoPxGpl` address.
  3. Then `AutoPxGpl` has no pending rewards but the balance of `pxGmx` and `weth` of contract has been increased.
  4. If anyone calls `AutoPxGpl.compound()` because there is no pending rewards contract would receive no rewards and because contract only calculates fee and rewards based on received rewards during the call to `compound()` so contract wouldn’t calculate any fee or reward accrual for those 1000 `pxGmx` and `weth` rewards.
  5. `owner` of `AutoPxGpl` would lose his fee for those rewards and users of `AutoPxGpl` would lose their claims for those 1000 `pxGmx` rewards (because the calculation for them didn’t happen).

This bug is because of the fact that the only logic handling rewards is in `compound()` function which is only handling receiving rewards by calling `claim()` during the call to `compound()` but it’s possible to call `claim()` directly (`PirexRewards` contract allows this) and `AutoPxGpl` won’t get notified about this new rewards and the related logics won’t get executed.

## Recommendation

Contract should keep track of it’s previous balance when `compound()` get executed and update this balance in deposits and withdraws and claims so it can detect rewards that directly transferred to contract without call to `compound()`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the AutoPxGmx and AutoPxGlp vault contracts calculate protocol fees and user reward accruals. Both contracts rely on a single function, `compound()`, to collect pending rewards from the PirexRewards module, measure the amount received by comparing token balances before and after the `claim()` calls, compute a platform fee on that delta, and finally update the reward accounting by calling internal harvest functions. Because the fee and reward logic is tied exclusively to the execution of `compound()`, any reward that arrives in the vault without that function being invoked remains invisible to the accounting code. The PirexRewards contract exposes a public `claim(address token, address user)` method that can be called by anyone for any user address. An attacker can therefore call `PirexRewards.claim(pxGmx, AutoPxGlp)` (and similarly for the GMX reward) directly, causing the reward tokens to be transferred into the AutoPxGlp contract without triggering `compound()`. As a result, the vault’s internal balance‑delta calculations see no change in `totalAssets()` or `pxGmx` balance during a later `compound()` call, so the platform fee (`totalPxGlpFee` and `totalPxGmxFee`) is calculated as zero and never transferred to the owner. Moreover, the `_harvest()` function that updates the per‑user `pxGmx` reward accrual is only called inside `compound()` when `pxGmxAmountOut` is non‑zero; bypassing this path means that the newly received `pxGmx` rewards are never harvested, leaving users without the expected reward distribution. From a user’s perspective, the vault appears to have received additional tokens, yet no fee is paid to the protocol and the expected reward payouts are missing – users may see their reward balance stay unchanged or even drop, and the protocol owner loses the fee that should have been collected. The issue manifests whenever there are pending rewards in the PirexRewards module and an attacker can invoke `claim()` directly, which is possible because the contract does not restrict the caller or enforce a callback mechanism. This bug was discovered during a security audit that examined the reward‑collection flow and noticed that `compound()` is the sole place where reward deltas are measured, while the external `claim()` function is publicly accessible. The problem is difficult to spot in ordinary testing because the token balances do increase, but the fee transfer events are absent and no error is thrown, making the loss appear as a silent accounting discrepancy. To remediate the issue, the contracts should maintain a persistent record of the vault’s token balances and update this record not only inside `compound()` but also after any direct token receipt, such as through a dedicated synchronization function or by restricting `claim()` to be callable only by the vault itself. Additionally, the fee‑calculation logic should be decoupled from the specific `compound()` flow and be triggered whenever the token balance of the vault changes, ensuring that protocol fees are always accounted for and that user reward accruals are properly harvested regardless of how the rewards are transferred.
