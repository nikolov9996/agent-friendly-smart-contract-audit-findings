---
id: 25399
severity: "Crit/High"
---

# Increasing emissionEnd after the previous emissionEnd ended will yield full rewards according to newEmissionEnd - prevEmissionEnd

## Description

Rewards are emitted at a certain rewardRate, which means stakers that have been staking for longer receive more rewards. However, there is an edge case in which this does not happen.

When the emissionEnd is reached, lastApplicableTime() will always be emissionEnd. This means that anyone who stakes after emissionEnd, no matter how much time after it, will have the same rewardDebt stored.

Thus, if the emissionEnd is increased after it has ended, every staker will receive the same rewards according to newEmissionEnd - prevEmissionEnd, even if they have staked in the same block that the emissionEnd was increased.

Putting this thought into numbers, if emissionEnd = 10, and if at block.timestamp = 15, a new emissionEnd is set to 20, stakers that staked from the beginning will get rewards pro-rata to 15-10 at the current timestamp, the same as stakers who staked at the current block.timestamp = 15, if they frontrun the setEmissionDetails() call.

## Proof of Concept

No PoC provided.

## Recommendation

The protocol decided to remove this functionality.
