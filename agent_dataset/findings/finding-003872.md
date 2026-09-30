---
id: 3872
severity: "High"
---

# Validators can front run calls to addIncentive to drain the entire incentive allocation in return for validating a single block

## Description

addIncentive is a function that allows anyone to allocate any amount of whitelisted incentive tokens to the BerachainRewardsVault contract to further incentivize validators for allocating BGT tokens to their vaults. In the current version of the code, the function allows the caller to set the incentive rate (only bounded by MAX_INCENTIVE_RATE) in case the amount of incentive tokens left in the contract is less than minIncentiveRate. As seen in the issue "Validators can manipulate incentive rates to receive more incentives than intended", rogue validators can set the incentiveRate as they wish to effectively steal leftover amounts. In this issue we will describe an attack vector that uses the same vulnerability but may end up in greater damage. Using the same parameters used in "Validators can manipulate incentive rates to receive more incentives than intended", in case addIncentive is called when incentive.amountRemaining < minIncentiveRate for a specific token (this can either happen during the first call or when the current rewards are consumed and need to be refilled). In the normal case we assume that the caller is planning to load the contract with a considerably large amount of tokens that will be consumed in accordance to his provided incentive rate. Potential attackers can monitor the mem-pool and sandwich the call to addIncentive with two calls:  
1. Before: call addIncentive with amount=101 (an amount slightly greater than minIncentiveRate) and incentiveRate=MAX_INCENTIVE_RATE.  
Now the victim's call of addIncentive(amount = 100,000 incentive tokens, incentiveRate = 100) is processed, they expect it to set the incentive rate to 100, but it would not because of the "donation" just made before, so line 329 won't be executed but the call will succeed. At this point incentive.amountRemaining is 100,101 incentive tokens.  
```solidity
if (amountRemaining <= minIncentiveRate && incentiveRate >= minIncentiveRate) {
    incentive.incentiveRate = incentiveRate; // line 329
}
```
2. After: call distributeFor and potentially siphon the entire 100,101 incentive tokens for just a single validated block since amount will be min(100101*1e18, 0.5 * 1e18 * 1e36 / 1e18) = 100,101 incentive tokens.  
```solidity
uint256 amount = FixedPointMathLib.mulDiv(bgtEmitted, incentive.incentiveRate, PRECISION);
uint256 amountRemaining = incentive.amountRemaining;
amount = FixedPointMathLib.min(amount, amountRemaining);
```

## Proof of Concept

no poc

## Recommendation

Providing a simple and hermetic solution to this issue is not an easy task. The issue stems from the fact that setting the incentive rate can be done in a permission-less way and therefore can be manipulated. While there can be a solution that will provide an efficient isolation for different callers of addIncentive, it will not be a simple one, but it might be inspired by the design that's used in Drips Protocol. With that being said, together with the Berachain team, we came up with a solution that is somewhat a compromise. Rather than completely solving the issue, we change the code so that attackers will only be able to temporarily DoS specific calls to addIncentive paying for each attack transaction slightly more than minIncentiveRate which will dis-incentivize them to do so. Please consider adopting this amended version of addIncentive, notice that it will also solve "Validators can manipulate incentive rates to receive more incentives than intended":  
```solidity
/// @inheritdoc IBerachainRewardsVault
function addIncentive(address token, uint256 amount, uint256 incentiveRate) external
onlyWhitelistedToken(token) {
    if (incentiveRate > MAX_INCENTIVE_RATE) IncentiveRateTooHigh.selector.revertWith();
    Incentive storage incentive = incentives[token];
    (uint256 minIncentiveRate, uint256 incentiveRateStored, uint256 amountRemaining) =
    (incentive.minIncentiveRate, incentive.incentiveRate, incentive.amountRemaining);
    if (amount < minIncentiveRate) AmountLessThanMinIncentiveRate.selector.revertWith();
    token.safeTransferFrom(msg.sender, address(this), amount);
    incentive.amountRemaining = amountRemaining + amount;
    // if its different, then caller is trying to change the incentive rate
    // validate if change is possible if not revert to avoid front running of caller call
    if (incentiveRate != incentiveRateStored){
        // Allow to reset incentive rate if amountRemaining < minIncentiveRate
        if (amountRemaining == 0 && incentiveRate >= minIncentiveRate) {
            incentive.incentiveRate = incentiveRate;
        }
        // if reset not possible, caller trying to increase the rate, validate if possible
        else if (incentiveRate >= incentiveRateStored) {
            uint256 rateDelta;
            unchecked {
                rateDelta = incentiveRate - incentiveRateStored;
            }
            if (amount >= FixedPointMathLib.mulDiv(amountRemaining, rateDelta, incentiveRateStored)) {
                incentive.incentiveRate = incentiveRate;
            } else {
                revert();
            }
        }
        else{
            // This will break the POC as front run tx will increase `amountRemaining` just more than `minIncentiveRate`
            // also they will set the `incentiveRateStored` to max so both condition will fail and you revert
            revert();
        }
    }
    emit IncentiveAdded(token, msg.sender, amount, incentive.incentiveRate);
}
```
Please note that the provided code is experimental and should be tested and as explained above is a practical compromise and not a holistic solution.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a front‑running manipulation of the permissionless addIncentive function that allows a validator to set the incentive rate under a specific edge case and then drain the entire incentive allocation in a single block. The root cause lies in the contract logic that permits any caller to change the incentiveRate whenever incentive.amountRemaining is less than or equal to minIncentiveRate, without requiring additional checks or isolation of the caller’s intent. Because the rate can be overwritten by anyone in this state, an attacker can monitor the mem‑pool, submit a tiny addIncentive transaction with the maximum allowed incentiveRate, and cause the contract to record a high rate while only adding a minimal amount of tokens. When a legitimate user later submits a larger addIncentive call expecting to set a lower rate, the condition on line 329 is bypassed, leaving the previously injected high rate in place and the amountRemaining just above the minimum threshold. The attacker then calls distributeFor, which calculates the reward as the minimum of the product of the emitted BGT amount and the inflated incentiveRate and the amountRemaining. Since the amountRemaining is now just above the minimum, the calculation yields the full token balance, allowing the attacker to claim the entire incentive pool for a single validated block. This results in the loss of incentive tokens, unfair reward distribution, and a breach of the protocol’s economic assumptions. The issue manifests only when the incentive pool is low – either on the first funding or after previous rewards have been exhausted – making it easy to miss during normal testing because the usual path (with sufficient amountRemaining) behaves correctly. The affected parties include validators who rely on predictable rewards, token holders whose incentives are depleted, and the protocol itself, which can no longer guarantee proper incentive accounting. The flaw was discovered during a security audit that examined the addIncentive logic and identified that the incentiveRate could be set without proper permission checks. Detecting the exploit in production can be difficult because the contract does not emit explicit warnings when the rate is overwritten, and the UI may simply show a sudden drop of the incentive balance or a single validator receiving an unexpectedly large reward. To remediate, the contract should prevent arbitrary rate changes when the pool is low, for example by requiring that any rate adjustment be accompanied by a sufficient token deposit to cover the increase, by restricting rate changes to a privileged role, or by adopting a commit‑reveal or isolated‑per‑caller design similar to the Drips Protocol. The proposed code adds validation that only allows a rate reset when the pool is empty and otherwise requires the caller to provide enough tokens to justify the rate delta, thereby raising the cost of front‑running attacks and mitigating the incentive drain.
