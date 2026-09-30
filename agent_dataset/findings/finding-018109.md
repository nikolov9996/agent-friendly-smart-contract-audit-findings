---
id: 18109
severity: "High"
---

# Rewards will be locked in LQTYStaking Contract

## Description

The state variable `F_Collateral` in the LQTYStaking contract is used to keep track of rewards for each of the collateral types used in the protocol. Every time the LQTYStaking contract is sent collateral assets for rewards by the ActivePool or the RedemptionHelper, `LQTYStaking.increaseF_Collateral` is called to record the rewards that are to be distributed to stakers.

However, if the state variable `totalLQTYStaked` is large enough in the LQTYStaking contract, zero rewards will be distributed to stakers even though LQTYStaking received assets. This issue is exacerbated when using WBTC as collateral due to its low number of decimals.

For example, given the following:

  1. `totalLQTYStaked` = 1e25; LQTY/OATH token has 18 decimals; this means that a total of 10 million LQTY has been staked
  2. A redemption rate of 0.5% was applied on a redemption of 10e8 WBTC. This leads to a redemption fee of 5e6 WBTC that is sent to the LQTYStaking contract. This happens in [this code](https://github.com/code-423n4/2023-02-ethos/blob/main/Ethos-Core/contracts/RedemptionHelper.sol#L190-L197).
  3. Given the above, RedemptionHelper calls `LQTYStaking.increaseF_Collateral(WBTCaddress, 5e6)`

The issue is in this line in `increaseF_Collateral`:

```solidity
    if (totalLQTYStaked > 0) {collFeePerLQTYStaked = _collFee.mul(DECIMAL_PRECISION).div(totalLQTYStaked);}
```

`_collFee` = 5e6; `DECIMAL_PRECISION` = 1e18; `totalLQTYStaked` = 1e25

If we substitute the variables with the actual values and represent the code in math, it looks like:

```solidity
    (5e6 * 1e18) / 1e25 = 5e24 / 1e25 = 0.5
```

Since the result of that math is a value less than 1 and in Solidity/EVM we only deal with integers and division rounds down, we get 0 as a result. That means the below code will only add `0` to `F_Collateral`:

```solidity
    F_Collateral[_collateral] = F_Collateral[_collateral].add(collFeePerLQTYStaked);
```

So even though LQTYStaking received 5e6 WBTC in redemption fee, that fee will never be distributed to stakers and will remain forever locked in the LQTYStaking contract. The minimum amount of redemption fee that is needed for the reward to be recognized and distributed to stakers is 1e7 WBTC. That means at least 0.1 BTC in collateral fee is needed for the rewards to be distributed when there is 1 million total LQTY staked.

## Proof of Concept

First, comment out [this line](https://github.com/code-423n4/2023-02-ethos/blob/main/Ethos-Core/contracts/LQTY/LQTYStaking.sol#L178) in `increaseF_Collateral` to disable the access control. This allows us to write a more concise POC. It is fine since the issue has nothing to do with access control.

Add the following test case to the `Ethos-Core/test/LQTYStakingFeeRewardsTest.js` file after the `beforeEach` clause:

```solidity
    it('does not increase F collateral even with large amount of collateral fee', async () => {
        await stakingToken.mint(A, dec(10_000_000, 18))
        await stakingToken.approve(lqtyStaking.address, dec(10_000_000, 18), {from: A})
        await lqtyStaking.stake(dec(10_000_000, 18), {from: A})

        const wbtc = collaterals[1].address
        const oldWBTC_FCollateral = await lqtyStaking.F_Collateral(wbtc)

        // .09 WBTC in redemption/collateral fee will not be distributed as reward to stakers
        await lqtyStaking.increaseF_Collateral(wbtc, dec(9, 6))
        assert.isTrue(oldWBTC_FCollateral.eq(await lqtyStaking.F_Collateral(wbtc)))

        // at least 0.1 WBTC in redemption/collateral fee is needed for it to be distributed as reward to stakers
        await lqtyStaking.increaseF_Collateral(wbtc, dec(1, 7))
        assert.isTrue(oldWBTC_FCollateral.lt(await lqtyStaking.F_Collateral(wbtc)))
    })
```

The test can then be run with the following command:

```bash
    $ npx hardhat test --grep "does not increase F collateral even with large amount of collateral fee"
```

## Recommendation

One way to address this issue is to use the same error-recording logic found in the `_computeLQTYPerUnitStaked` logic that looks like:

```solidity
    uint LQTYNumerator = _LQTYIssuance.mul(DECIMAL_PRECISION).add(lastLQTYError);

    uint LQTYPerUnitStaked = LQTYNumerator.div(_totalLUSDDeposits);
    lastLQTYError = LQTYNumerator.sub(LQTYPerUnitStaked.mul(_totalLUSDDeposits));
```

The `lastLQTYError` state variable stores the LQTY issuance that was not distributed since they were just rounded off. The same approach can be used in `increaseF_Collateral`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reward‑distribution rounding error in the LQTYStaking contract. The contract stores a per‑collateral reward accumulator called F_Collateral and updates it in increaseF_Collateral by computing collFeePerLQTYStaked = _collFee * DECIMAL_PRECISION / totalLQTYStaked. Because Solidity uses integer arithmetic, any division that yields a value smaller than one is rounded down to zero. When the total amount of LQTY staked (totalLQTYStaked) is large – for example 1e25 (10 million LQTY with 18 decimals) – and the collateral fee received from a redemption is modest – such as 5e6 WBTC units (0.09 WBTC) – the product of the fee and the precision constant (5e6 * 1e18) divided by the huge stake amount results in 0 after truncation. Consequently the contract adds zero to F_Collateral, leaving the fee permanently locked inside the staking contract. The root cause is the lack of an error‑accumulation mechanism for the fractional remainder that is discarded by integer division. The bug can be triggered whenever a redemption fee or any other collateral reward is smaller than the threshold required to produce a non‑zero per‑LQTY reward, which is especially common for low‑decimal assets like WBTC. From a user’s perspective the symptom is that stakers see no increase in their pending rewards or accrued balance even though the protocol’s treasury has received collateral; the UI may show a growing contract balance but individual reward counters remain unchanged, leading to confusion and the perception that “my rewards are missing”. The impact is that legitimate rewards are never distributed, effectively stealing value from stakers and breaking the protocol’s accounting assumptions about fair reward sharing. The issue was discovered during a formal audit when test cases demonstrated that calling increaseF_Collateral with a fee just below the rounding threshold did not change F_Collateral, while a fee above the threshold did. The problem is subtle because the contract’s balance does increase, so a superficial inspection of token transfers may not reveal the hidden loss. The recommended mitigation is to adopt an error‑recording pattern similar to the _computeLQTYPerUnitStaked function: compute the numerator with the precision factor, add the previously stored remainder, perform the division, and then store the new remainder (lastLQTYError) for future calls. This ensures that fractional rewards are accumulated over time and eventually distributed, preventing permanent locking of small fees. In broader terms, the bug belongs to the class of integer‑division rounding errors that cause reward or fee accruals to be silently dropped when the divisor is large relative to the dividend, a common pitfall in financial smart contracts that rely on fixed‑point arithmetic.
