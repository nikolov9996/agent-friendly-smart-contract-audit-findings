---
id: 5753
severity: "Critical"
---

# Excessive Payout in unstake and claim Functions Causes Severe Fund Loss

## Description

The unstake and claim functions incorrectly calculate the amount to transfer, resulting in users receiving 12 times the amount they originally staked. This leads to a significant loss of funds for the protocol.
The flawed calculation is shown here:
```solidity
let amount_to_transfer = self.position.amount
+ (self.position.amount * (12 - self.position.claimed as u64) * 10025 / 10000);
```
This miscalculation causes users to receive an excessive reward, far exceeding the intended staking rewards.

## Proof of Concept

no poc

## Recommendation

The correct implementation should ensure that only a small portion of the staked amount is transferred per claim. Corrected Claim Function Calculation:
```solidity
let amount_to_transfer = self.position.amount * 25 / 10000;
```
Corrected Unstake Function Calculation: To properly transfer the unclaimed amount after the staking duration has passed:
```solidity
let amount_to_transfer =
self.position.amount + ((12 - self.position.claimed as u64) * self.position.amount * 25 / 10000);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic mis‑calculation in the contract’s unstake and claim functions that determines how much token is transferred back to a staker. Instead of a modest reward proportional to the original stake, the code multiplies the staked amount by a factor that can be as high as twelve and adds an inflated percentage (10025/10000) for each unclaimed period. The root cause is an incorrect formula that uses the expression (12‑claimed) together with a 10025/10000 multiplier, which dramatically over‑estimates the payout. When a user invokes claim or unstake, the contract computes amount_to_transfer = position.amount + (position.amount * (12‑claimed) * 10025 / 10000). Because the multiplier exceeds 1 and the factor (12‑claimed) can be up to twelve, the resulting transfer can be roughly twelve times the original stake. An attacker can simply call claim or unstake and receive an excessive reward, draining the protocol’s liquidity. The impact is severe fund loss: the protocol pays out far more than it receives, potentially exhausting its treasury and breaking the economic model. The condition for exploitation is any call to the affected functions after a stake has been created; the bug manifests whenever the claimed counter is less than twelve, which is the normal case for most users. All participants who stake tokens are affected – stakers receive unexpectedly large payouts, while the protocol and other users lose the funds that should have remained in the pool. The issue was discovered during a manual audit by Spearbit, who identified the formula as inconsistent with the intended reward schedule. It can be hard to notice because the numbers may appear plausible in isolation and the contract does not emit explicit warnings; only a thorough review of the reward logic reveals the over‑payment. To remediate, the calculation should be replaced with a modest fixed‑rate reward, for example amount_to_transfer = position.amount * 25 / 10000 for a claim, and for unstake the payout should be position.amount plus the unclaimed portion calculated with the same small rate. The fix removes the erroneous 12‑multiplier and the 10025/10000 factor, ensuring that only the intended tiny fraction of the stake is paid out per claim and that the full principal is returned on unstake. From a user’s perspective, the contract currently shows a reward that looks like a bonus but actually empties the pool; users expect a modest interest but may see their balance increase dramatically, which is a symptom of the bug. The bug belongs to the class of “incorrect financial formula” or “reward over‑payment” vulnerabilities, where arithmetic errors break accounting assumptions and cause money to disappear from the system.
