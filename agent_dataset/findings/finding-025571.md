---
id: 25571
severity: "Crit/High"
---

# Vault portion calculation in PrizePool::getVaultPortion() is incorrect as _startDrawIdInclusive has been erased

## Description



## Proof of Concept

## Vulnerability Detail

To illustrate the issue, consider the grand prize, where odds are `1 / g = 0.00273972602e18` with `g == 365 days`. The [estimated](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L1014>) prize frequency is `1e18 / 0.00273972602e18 == 365.000000985` rounded up to the nearest integer, `366`. If `lastAwardedDrawId_` is `366`, then `startDrawIdInclusive` is `366 - 366 + 1 == 1`. This means that it will fetch the total, vault and donation accumulators since the opening of `drawId == 1`.

However, when `lastAwardedDrawId_ == 366`, the current open `drawId` is `367`, which is written to index 0 in the circular buffer, overwriting `drawId == 1`. But, in the donation and vault cases, the accumulator still has `drawId == 1`, as the buffer will likely not have been overwritten (draw periods take 1 day, it is highly likely the individual accumulators are not written to every day, but the total accumulator is, or users may exploit this on purpose). As the buffer is circular, this will keep happening every time after the buffer has been filled and indexes start being overwritten.

Thus, due to this, the vault portion will be bigger than it should, as the total accumulator is calculated between 365 days (from 2 to 366, as 1 has been erased), but the vault and donation accumulators for 366 days (between 1 and 366). Users will have bigger than expected chances of winning prizes and in the worst case, they may even not be able to claim prizes at all, in case the erased `drawId` had a significant contribution to the prizes through a donation, and then it underflows when doing `totalSupply = totalContributed - totalDonated;` in [PrizePool::getVaultShares()](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L1129>).

Add the following test to `PrizePool.t.sol` and log the vault and total portions in `PrizePool::getVaultShares()`. The contribution of the vault will be bigger than the total.

```solidity
function testAccountedBalance_POC() public {
  for (uint i = 0; i < 366; i++) {
    contribute(100e18);
    awardDraw(1);
    mockTwab(address(this), msg.sender, 0);
  }
  address otherVault = makeAddr("otherVault");
  vm.prank(otherVault);
  prizePool.contributePrizeTokens(otherVault, 0);
  uint256 prize = claimPrize(msg.sender, 0, 0);
}
```

## Impact

Users get better prize chances than supposed and/or it can lead to permanent reverts when trying to claim prizes.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L1014](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L1014>)

## Recommendation

When calculating `PrizePool::computeRangeStartDrawIdInclusive()`, the `rangeSize` should be capped to `365` to ensure the right `startDrawIdInclusive` is fetched, not one that has already been erased. In the scenario above, if the range is capped at 365, when `lastAwardedDrawId_ == 366`, `startDrawIdInclusive` would be `366 - 365 + 1 == 2`, which has not been erased as the current `drawId` is `367`, having only overwritten `drawId == 1`, but 2 still has the information.
