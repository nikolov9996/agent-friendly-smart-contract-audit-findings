---
id: 17719
severity: "High"
---

# Auctions can end in epoch after intended,

## Description

When liens are liquidated, the router checks if the auction will complete in a future epoch and, if it does, sets up a liquidation accountant and other logistics to account for it. However, the check for auction completion does not take into account extended auctions, which can therefore end in an unexpected epoch and cause accounting issues, losing user funds. The liquidate() function performs the following check to determine if it should set up the liquidation to be paid out in a future epoch:
```solidity
if (PublicVault(owner).timeToEpochEnd() <= COLLATERAL_TOKEN.auctionWindow())
```
This function assumes that the auction will only end in a future epoch if the auctionWindow (typically set to 2 days) pushes us into the next epoch. 15 minutes. In these cases, auctions are extended repeatedly, up to a maximum of 1 day.
```solidity
if (firstBidTime + duration - block.timestamp < timeBuffer) {
    uint64 newDuration = uint256(
        duration + (block.timestamp + timeBuffer - firstBidTime)
    ).safeCastTo64();
    if (newDuration <= auctions[tokenId].maxDuration) {
        auctions[tokenId].duration = newDuration;
    } else {
        auctions[tokenId].duration =
            auctions[tokenId].maxDuration -
            firstBidTime;
    }
    extended = true;
}
```
The result is that there are auctions for which accounting is set up for them to end in the current epoch, but will actual end in the next epoch. Users who withdrew their funds in the current epoch, who are entitled to a share of the auction's proceeds, will not be paid out fairly.

## Proof of Concept

no poc

## Recommendation

Change the check to take the possibility of extension into account:
```solidity
if (PublicVault(owner).timeToEpochEnd() <= COLLATERAL_TOKEN.auctionWindow() + 1 days)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect epoch‑boundary check performed when a collateral lien is liquidated. The router decides whether to schedule the liquidation payout for a future epoch by comparing the remaining time until the current epoch ends with the auctionWindow parameter. This comparison assumes that the auction will finish within the fixed auctionWindow (typically two days) and therefore will not cross into the next epoch. However, the auction contract contains an extension mechanism that can lengthen the auction by up to one day when a bid arrives close to the end of the current duration. Because the router’s check does not consider this possible extension, it may record the liquidation as if it will settle in the current epoch while the auction actually continues into the following epoch. When users withdraw their funds in the current epoch, they are entitled to a share of the auction proceeds, but the accounting logic believes the auction has already concluded and therefore does not allocate any payout to those users. As a result, affected participants receive less than expected or lose their entitled share, effectively causing a loss of funds. The issue manifests only when an auction is extended past the epoch boundary – a situation that can be triggered by placing a bid within the timeBuffer period defined in the auction contract. It is difficult to notice because the discrepancy appears only at the moment of epoch transition, and the accounting tables may look correct until the payout is attempted. The flaw was discovered during a manual audit that examined the liquidation flow and identified that the epoch‑check logic ignored the extension path. To remediate the problem, the epoch‑check should be amended to include the maximum possible extension (for example, adding one day to the auctionWindow) or, more robustly, compute the projected final auction timestamp after any extensions before deciding on the payout epoch. This change ensures that the accounting setup matches the actual auction termination time, preserving the fairness of fund distribution and preventing inadvertent loss of user assets.
