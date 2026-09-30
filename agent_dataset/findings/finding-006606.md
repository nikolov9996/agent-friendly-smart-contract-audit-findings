---
id: 6606
severity: "High"
---

# Index can reach type(uint104).max when asset totalSupply is dust and DoS aToken transfers indefinitely

## Description

The reward formula in Reward Distributors (RewardsDistributor.sol and RewardsDistributor6909.sol) uses an index to track accrual of rewards per unit of aToken held. The size for the index is set to be uint104, and it should be well enough for cases when assetTotalSupply >= 10**assetDecimals or decimals is a low value. However in the case totalSupply is dust, even for a short amount of time, the index can reach type(uint104).max, and no further reward accrual can happen:
• RewardsDistributor.sol#L279:
```solidity
if (newIndex != oldIndex) {
    require(newIndex <= type(uint104).max, "Index overflow"); // <<<
    //optimization: storing one after another saves one SSTORE
    rewardConfig.index = uint104(newIndex);
    rewardConfig.lastUpdateTimestamp = uint32(block.timestamp);
    emit AssetIndexUpdated(asset, reward, newIndex);
} else {
    rewardConfig.lastUpdateTimestamp = uint32(block.timestamp);
}
```
The formula for computing the index is given below:
• RewardsDistributor.sol#L501:
```solidity
uint256 currentTimestamp = block.timestamp > distributionEnd ? distributionEnd : block.timestamp;
uint256 timeDelta = currentTimestamp - lastUpdateTimestamp;
return (emissionPerSecond * timeDelta * (10 ** decimals)) / totalBalance + currentIndex;
```
emissionPerSecond is the number of reward tokens to emit globally per second. decimals is the decimals precision for asset token considered. totalBalance is the total supply of the asset token considered.
Scenario:
• Preconditions:
Parameter
Value
Asset token
aWeth (decimals: 18)
Reward token
DAI (decimals: 18)
Total reward amount (A)
1000 DAI
Total asset supply
Time elapsed (t)
12 sec (~1 block)
Distribution duration (T)
1 month
Very reasonable values except for total asset supply which may need some stars to align.
• Index calculation: First let's calculate emissionPerSecond denoted r:
r = A/T = (1000 * 10**18)/262800 = 3.8 * 10**14 Which yields the index value:
i = r*t*10**d = (3.8 * 10**14) * 12 * 10**18 = 4.56 * 10**34 > 2**104

## Proof of Concept

no poc

## Recommendation

Multiple recommendations can be considered:
• Increasing index size: When A = 1_000_000e18 and d = 18, index would be safe from reverting using uint140.
• Do not accrue index when normalized total supply is below a threshold (which should not happen anyway in any reasonable case):
```solidity
if (
    emissionPerSecond == 0 ||
    totalBalance == 0 ||
    (decimals == 18 && totalBalance <= UPDATE_THRESHOLD) || // @audit ok to be below threshold for low decimal tokens
    lastUpdateTimestamp == block.timestamp ||
    lastUpdateTimestamp >= distributionEnd
) {
    return currentIndex;
}
```
Additionally to avoid reverting at any costs during action handling, overflow could be allowed so the index would naturally wrap around (it would be safe since we only use index differences when computing rewards).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow in the reward‑distribution index used by the RewardsDistributor contracts. The index, which records cumulative rewards per unit of aToken, is stored in a uint104 variable under the assumption that the underlying asset’s total supply will always be at least 10**decimals. The update formula multiplies the global emission rate per second by the elapsed time and by 10**decimals, then divides by the total balance of the asset before adding the result to the current index. When the total balance becomes extremely small – for example when the asset supply is reduced to dust – the division denominator shrinks dramatically and the numerator can exceed the maximum value representable in 104 bits. The require statement that checks newIndex <= type(uint104).max then triggers, causing the transaction that attempts to update rewards to revert. This situation can be triggered deliberately by an attacker who forces the asset supply to drop below a safe threshold, for instance by withdrawing almost all tokens or by deploying a new token with a tiny supply, and then waiting a few seconds for the index calculation to overflow. Once the overflow condition is reached, any subsequent call that tries to accrue or claim rewards for that asset will revert, effectively denying service to all participants. The impact is that users who expect to earn or claim rewards see no accrual; the UI may display zero pending rewards, reward‑claim transactions fail with an “Index overflow” error, and the protocol’s incentive mechanism is broken, potentially eroding trust and leaving allocated reward funds unclaimed. The bug occurs only when the totalSupply is dust and a non‑zero amount of time passes, conditions that are rare in normal operation and therefore easy to miss during testing. It was discovered during a formal audit by Spearbit, which identified the unsafe assumption about totalSupply size and the lack of a guard against tiny balances. The issue belongs to the class of integer‑width overflow bugs in financial accounting logic, where insufficient bit‑width combined with a division by a very small denominator leads to a wrap‑around or revert that can be exploited for denial‑of‑service. To remediate, the index should be stored in a larger integer type (e.g., uint140) that can accommodate extreme values, or the contract should skip index updates when totalBalance falls below a predefined safe threshold, or allow the index to wrap safely because only differences are used in reward calculations. Adding explicit checks for zero or dust balances before performing the multiplication would also prevent the overflow and restore reliable reward distribution.
