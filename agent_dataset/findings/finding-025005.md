---
id: 25005
severity: "Low/Info"
---

# Missing maxRedeem() implementation

## Description



## Proof of Concept

## Vulnerability Detail

When we look at `sYUSD::maxWithdraw()`, it correctly accounts for the locked shares:

```solidity
function maxWithdraw(address owner) public view virtual override returns (uint256) {
    // Calculate current unlocked amount (without state changes)
    uint256 currentUnlocked = unlockedShares[owner];
    LockedShares[] storage userLocks = userLockedShares[owner];

    for (uint256 i = 0; i < userLocks.length; i++) {
        if (block.timestamp >= userLocks[i].expiryTimestamp) {
            currentUnlocked += userLocks[i].amount;
        }
    }

    // Convert unlocked shares to assets
    return convertToAssets(currentUnlocked);
}
```

However, this is not true for `maxRedeem()`, which returns the inherited unchanged `balanceOf(user)` from `ERC4626`.

## Impact

Specification mismatch.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-aegis-staked-yusd/blob/foundry-tests/aegis-contracts/contracts/sYUSD.sol#L17](<https://github.com/sherlock-audit/2025-04-aegis-staked-yusd/blob/foundry-tests/aegis-contracts/contracts/sYUSD.sol#L17>)

## Recommendation

Implement `maxRedeem()`, for example:

```solidity
function maxRedeem(address owner) public view virtual override returns (uint256) {
    // Calculate current unlocked amount (without state changes)
    uint256 currentUnlocked = unlockedShares[owner];
    LockedShares[] storage userLocks = userLockedShares[owner];

    for (uint256 i = 0; i < userLocks.length; i++) {
        if (block.timestamp >= userLocks[i].expiryTimestamp) {
            currentUnlocked += userLocks[i].amount;
        }
    }

    return currentUnlocked;
}
```
