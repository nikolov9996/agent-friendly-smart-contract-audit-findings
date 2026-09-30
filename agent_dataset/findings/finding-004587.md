---
id: 4587
severity: "High"
---

# Price could have a max drop even if it has oversold Submitted by deadrosesxyz

## Description

The protocol utilizes a dutch-auction bonding curve. The idea is that the price drops until the point where volume picks up. To put it very simply, if not enough tokens are bought, price drops more. And ideally, if enough tokens are bought, token's price starts rising.
```solidity
// Get the expected amount sold and the net sold in the last epoch
uint256 expectedAmountSold = _getExpectedAmountSoldWithEpochOffset(0);
int256 netSold = int256(totalTokensSold_) - int256(state.totalTokensSoldLastEpoch);
state.totalTokensSoldLastEpoch = totalTokensSold_;
// Possible if no tokens purchased or tokens are sold back into the pool
if (netSold <= 0) {
    adjustmentTick = upperSlugPosition.tickLower;
    accumulatorDelta += _getMaxTickDeltaPerEpoch();
} else if (totalTokensSold_ <= expectedAmountSold) {
    // Safe from overflow since we use 256 bits with a maximum value of (2**24-1) * 1e18
    adjustmentTick = currentTick;
    accumulatorDelta += _getMaxTickDeltaPerEpoch()
        * int256(WAD - FullMath.mulDiv(totalTokensSold_, WAD, expectedAmountSold)) / I_WAD;
} else {
```
The problem is however in the current implementation. The first check on which depends the price movement is the epoch-to-epoch movement. As we can see, if netSold <= 0, nothing else is considered and price has a max drop. This is even in the cases where tokens are sold in excess to many upcoming epochs. For example, til end of epoch 2, there might be sold the quota that should usually be until epoch 4. Then, if in epoch 3, the netSold is <= 0, there will be a significant drop in price, even though there are more tokens sold than what is usually expected for said epoch.
This could be extremely problematic in scenarios where a token has rapidly picked up momentum which temporarily stagnates throughout an epoch. Such price could easily make the whole token crash as new users would be able to buy it at significantly lower price.

Impact Explanation:
Issue could potentially crash the whole economics surrounding a token, therefore should be High severity.

## Proof of Concept

Attaching 2 tests. In both of them assets have been sold in excess for next epochs. In one of the tests just 1 wei is bought in the following epoch, while in the other no more assets are bought. Because of this, price drops ~800 ticks:
```solidity
function test_offByOne1() public {
    vm.warp(hook.getStartingTime() + hook.getEpochLength());
    uint256 expectedAmountSold = hook.getExpectedAmountSoldWithEpochOffset(3); // this should return
    PoolKey memory poolKey = key;
    buy(int256(expectedAmountSold));
    vm.warp(hook.getStartingTime() + 2 * hook.getEpochLength());
    buy(1);
    sell(1);
    vm.warp(hook.getStartingTime() + 3 * hook.getEpochLength());
    bool isToken0 = hook.getIsToken0();
    int24 tick = hook.getCurrentTick(poolKey.toId());
    console.log(isToken0);
    console.log(tick);
    buy(1);
    tick = hook.getCurrentTick(poolKey.toId());
    console.log(tick);
}

function test_offByOne2() public {
    vm.warp(hook.getStartingTime() + hook.getEpochLength());
    uint256 expectedAmountSold = hook.getExpectedAmountSoldWithEpochOffset(3); // this should return
    PoolKey memory poolKey = key;
    buy(int256(expectedAmountSold));
    vm.warp(hook.getStartingTime() + 2 * hook.getEpochLength());
    buy(1);
    // sell(1);
    vm.warp(hook.getStartingTime() + 3 * hook.getEpochLength());
    bool isToken0 = hook.getIsToken0();
    int24 tick = hook.getCurrentTick(poolKey.toId());
    console.log(isToken0);
    console.log(tick);
    buy(1);
    tick = hook.getCurrentTick(poolKey.toId());
    console.log(tick);
}
```

## Recommendation

First check should be whether expected assets are met and only if they're not, check if netBought is non-positive.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the price‑adjustment logic of a dutch‑auction bonding curve used by the protocol. The contract determines the next price tick by first checking whether the net amount of tokens sold during the current epoch (netSold) is non‑positive. If netSold <= 0 the code forces the price to move by the maximum allowed tick delta, regardless of how many tokens have actually been sold relative to the expected quota for that epoch. Because this check is performed before verifying whether the total tokens sold exceed the expected amount for the epoch, a situation can arise where the protocol has already sold more tokens than it would normally expect for several future epochs, yet a later epoch records no net purchases (or a net zero sale). In that case the early‑exit condition triggers a maximal price drop even though the overall supply pressure remains high. The root cause is an incorrect ordering of conditional statements that gives precedence to a generic “no‑sale” branch over the more specific “oversold” branch, effectively ignoring cumulative sales across epochs. An attacker can exploit this by arranging a large purchase that satisfies the expected quota in an early epoch, then allowing the next epoch to have zero or negative net sales. The contract will then apply the maximum tick delta, causing the token price to plunge dramatically – in the provided tests the price fell by roughly 800 ticks. From a user’s perspective the token suddenly becomes much cheaper; a buyer expecting a stable or rising price may instead see the price drop to near‑zero and can acquire tokens at an artificially low cost, while existing holders see the value of their holdings erode. The impact is a potential collapse of the token’s economic model, loss of confidence, and possible capital outflow as participants rush to sell or avoid buying. The bug manifests only under the specific pattern of overselling followed by a net‑zero epoch, making it easy to miss during casual testing because normal price trajectories appear correct. It was discovered during a formal audit when unit tests simulated oversold conditions and observed an unexpected large tick reduction. To remediate, the logic should first verify whether the total tokens sold are less than or equal to the expected amount for the epoch; only if that condition fails should the contract consider the netSold <= 0 case. Reordering the checks and ensuring that price adjustments account for cumulative oversold volume eliminates the unintended maximal drop and restores the intended price‑curve behavior.
