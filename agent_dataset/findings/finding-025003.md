---
id: 25003
severity: "Crit/High"
---

# Attacker can DoS user withdrawals at no cost

## Description



## Proof of Concept

## Vulnerability Detail

`sYUSD::deposit()` is as follows:

```solidity
function _deposit(
    address caller,
    address receiver,
    uint256 assets,
    uint256 shares
) internal virtual override {
    super._deposit(caller, receiver, assets, shares);

    // Add new locked shares entry
    userLockedShares[receiver].push(LockedShares({
        amount: shares,
        expiryTimestamp: block.timestamp + lockupPeriod
    }));
}
```

As can be seen, it pushes a new element each time it is called, via `sYUSD::deposit()` or `sYUSD::mint()`. An attacker can deposit to another user and fill their array. Then, when the user withdraws via `sYUSD::withdraw()` or `sYUSD::redeem()`, it loops through the array all at once and DoSes withdrawals due to OOG.

```solidity
function _withdraw(
    address caller,
    address receiver,
    address owner,
    uint256 assets,
    uint256 shares
) internal virtual override {
    // First update the unlocked shares
    updateUnlockedShares(owner);

    // Ensure user has enough unlocked shares
    if (unlockedShares[owner] < shares) {
        revert InsufficientUnlockedShares(shares, unlockedShares[owner]);
    }

    // Reduce unlocked shares
    unlockedShares[owner] -= shares;

    super._withdraw(caller, receiver, owner, assets, shares);
}

...

function updateUnlockedShares(address user) public {
    LockedShares[] storage userLocks = userLockedShares[user];

    for (uint256 i = 0; i < userLocks.length; i++) {
        if (block.timestamp >= userLocks[i].expiryTimestamp && userLocks[i].amount > 0) {
            unlockedShares[user] += userLocks[i].amount;
            userLocks[i].amount = 0;
        }
    }

    // Clean up empty entries
    _cleanupLockedShares(user);
}
```

Please find a POC [here](<https://github.com/sherlock-audit/2025-04-aegis-staked-yusd/blob/foundry-tests/aegis-contracts/test/SYUSD.t.sol#L403>).

## Impact

Stuck funds at no cost for an attacker.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-aegis-staked-yusd/blob/main/aegis-contracts/contracts/sYUSD.sol#L80-L92](<https://github.com/sherlock-audit/2025-04-aegis-staked-yusd/blob/main/aegis-contracts/contracts/sYUSD.sol#L80-L92>)

## Recommendation

Set a max iterations argument.
