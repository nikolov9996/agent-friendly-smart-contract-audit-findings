---
id: 16276
severity: "High"
---

# Level XP multiplier isn't updated on NFT level

## Description

Users have the ability to stake their NFTs to get XP in exchange. They can then use that XP to enter a raffle or level up their NFTs. Depending on the level of the NFT it has different multiplier bonuses. The problem is that when an NFT is level up the multiplier bonus is NOT updated.
```solidity
function levelUP(uint256 id)
    public
    nonReentrant
    isStakerOfAll(viewStakedNFTs(msg.sender))
    updateXP(msg.sender)
{
    if (stakedNFTs[msg.sender][getIndexOfItem(id)].NFTLevel == 1) {
        spendXP(levelTwoPrice, msg.sender);
        stakedNFTs[msg.sender][getIndexOfItem(id)].balance++;
    } else if (stakedNFTs[msg.sender][getIndexOfItem(id)].NFTLevel == 2) {
        spendXP(levelThreePrice, msg.sender);
        stakedNFTs[msg.sender][getIndexOfItem(id)].balance++;
    } else {
        revert("Your NFT reached max level.");
    }
}
```
There are state variables for the NFT level which are not used anywhere:
```solidity
uint256 levelTwoMultiplier = 2;
uint256 LevelThreeMultiplier = 3;
```

## Proof of Concept

no poc

## Recommendation

Update NFTXPMultiplier when leveling up NFT:
```solidity
function levelUP(uint256 id)
    public
    nonReentrant
    isStakerOfAll(viewStakedNFTs(msg.sender))
    updateXP(msg.sender)
{
    if (stakedNFTs[msg.sender][getIndexOfItem(id)].NFTLevel == 1) {
        spendXP(levelTwoPrice, msg.sender);
        stakedNFTs[msg.sender][getIndexOfItem(id)].balance++;
        stakedNFTs[msg.sender][getIndexOfItem(id)].NFTXPMultiplier = levelTwoMultiplier;
    } else if (stakedNFTs[msg.sender][getIndexOfItem(id)].NFTLevel == 2) {
        spendXP(levelThreePrice, msg.sender);
        stakedNFTs[msg.sender][getIndexOfItem(id)].balance++;
        stakedNFTs[msg.sender][getIndexOfItem(id)].NFTXPMultiplier = LevelThreeMultiplier;
    } else {
        revert("Your NFT reached max level.");
    }
}
```
Varonve.md

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract allows users to stake NFTs and earn experience points (XP) that can be spent on raffles or to level up the NFTs. Each NFT level is supposed to grant a higher XP multiplier, defined by the variables levelTwoMultiplier (value 2) and LevelThreeMultiplier (value 3). The levelUP function correctly deducts the required XP and increments the NFT balance, but it never updates the NFTXPMultiplier field that is used in later XP calculations. As a result, after an NFT is promoted from level 1 to level 2 (or from level 2 to level 3), the on‑chain record of the multiplier remains at its previous value. Consequently, the XP earned after leveling is calculated with the old, lower multiplier, so the user receives less XP than expected. From a user’s perspective the UI may show a higher NFT level, yet the XP accrual rate appears unchanged or even lower, leading to confusion such as “my NFT is level 2 but I still get the same XP as before” or “my raffle entries did not increase after leveling”. The bug originates from a logical omission: the state variables that store the multiplier are never written to during the level‑up process, and the contract does not derive the multiplier dynamically from the NFTLevel field. This condition is triggered every time a user calls levelUP, i.e., whenever an NFT is upgraded, and it affects all NFT owners who rely on XP for participation in the protocol’s economic mechanisms. The issue was discovered during a manual audit that inspected the levelUP implementation and noticed that the multiplier variables were declared but never referenced. It can be hard to notice because there is no explicit error; the contract continues to function, but the expected increase in XP is silently missing, which may only be observed through abnormal XP balances or reduced raffle chances. The vulnerability violates the business logic that higher NFT levels should provide proportionally higher rewards, breaking the accounting assumptions of the system. To remediate, the levelUP function should assign the appropriate multiplier to the NFTXPMultiplier field after a successful upgrade (e.g., setting it to levelTwoMultiplier for a level‑2 NFT and to LevelThreeMultiplier for a level‑3 NFT), or alternatively compute the multiplier on‑the‑fly from the NFTLevel value, ensuring that future XP calculations reflect the new level correctly.
