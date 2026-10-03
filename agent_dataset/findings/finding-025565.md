---
id: 25565
severity: "Medium"
---

# Claimers can receive less feePerClaim than they should if some prizes are already claimed or if reverts because of a reverting hook

## Description



## Proof of Concept

## Vulnerability Detail

Auctions for claiming prizes are based on the [VRGDA algorithm](<https://www.paradigm.xyz/2022/08/vrgda>) In simple terms, this algorithm update price depending on either the numbers of claim is behind or ahead of time schedule. In order to have a schedule, a target of claim per time unit is defined. Just to give an idea, let's simplify that to the extreme (we will see complete formula afterward) and say : `price(t) = claim/expected * targetPrice(t)` E.g: if 10 claims per 2 hours are exepected, then at t=1h, 5 claims should be concluded. If only 4 were claimed, then we can calculate that (4 claims)/(5 expected) < 1, price will be lower that target. if 6 were claimed, then we will have (6 claims)/(5 expected) > 1, price will be greater than target.

The formula that has been implemented into `LinearVRGDALib` is the following:

```haskell
price = p0 * e^ (k * (t - n+1/r))   ; with k = ln(maxFee/minFee) * t_target
```

With:

- `n` the number of claim already completed
- `r` the expected rate per hour
- `k` the decay constant (speed at which price will change)
- `p0` the target price (or fee in our case)

The more `k (t - n+1/r) > 0`*, the more `price > p0` When `t = n+1/r` <=> `(k `*` (t - n+1/r)) = 0`, then `price = p0` The more `k * (t - n+1/r) < 0`, the more `price < p0`

We understand that the more whe are behind schedule in term of expected claim, the higher the fees earned by claimer will be. And the more we are ahead of schedule, the lower the fee for claimers will be (as their is no urgency)

## Impact

The `feePerClaim` computation is incorrect as the VRGDA is calculated for more claims that will really happen, leading to less fee earned by claimers at the time of the call.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether//blob/main/pt-v5-claimer/src/Claimer.sol#L113](<https://github.com/sherlock-audit/2024-05-pooltogether//blob/main/pt-v5-claimer/src/Claimer.sol#L113>) [https://github.com/sherlock-audit/2024-05-pooltogether//blob/main/pt-v5-claimer/src/Claimer.sol#L236](<https://github.com/sherlock-audit/2024-05-pooltogether//blob/main/pt-v5-claimer/src/Claimer.sol#L236>)

## Recommendation

The `PrizePool` contract expose a function to check if a prize has already been claimed: `wasClaimed` This can be used to countClaims based on the actual true number of claimable prizes from the array.

This isn't a "perfect" solution though, as there are still issues when not already claimed prizes revert because of reverting prize hooks. In that case, VRGDA will still count the claim as happening, but we can consider this less likely to happen.

```diff
  function _countClaims(
    address[] calldata _winners,
    uint32[][] calldata _prizeIndices
  ) internal pure returns (uint256) {
    uint256 claimCount;
    uint256 length = _winners.length;
    for (uint256 i = 0; i < length; i++) {
-     claimCount += _prizeIndices[i].length;
+	  numPrize = _prizeIndices[i].length;
+	  for(uint256 j = 0; j < numPrize; j++) {
+     	bool wasClaimed = wasClaimed(_vault, _winner, _drawId,_tier, _prizeIndex);
+     	if(!wasClaimed) {
+		 claimCount += 1;
+		}
+     }
    }
    return claimCount;
  }
```
