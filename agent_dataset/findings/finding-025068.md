---
id: 25068
severity: "Crit/High"
---

# Reward Token Loss for LPs During NFT Position Transfer

## Description



## Proof of Concept

None

## Vulnerability Details

When an NFT position is transferred, the following function is called:

```solidity
function transferFrom(
    address from,
    address to,
    uint256 id
) public virtual override onlyIfPoolManagerLocked {
    super.transferFrom(from, to, id);   // Ownership is updated first
    if (positionInfo[id].hasSubscriber()) _unsubscribe(id);
}
```

- Ownership of the NFT position is changed first.
- _unsubscribe is then called, which triggers the notifyUnsubscribe logic.

```solidity
    function notifyUnsubscribe(
        uint256 tokenId
    ) external override onlyAuthorizedCaller {
        NotifyContext memory c = _buildContextFromToken(tokenId, true);

        dailyEpochGauge.notifyUnsubscribeWithContext(
            c.posKey,
            c.pidRaw,
            c.currentTick,
            c.owner,
            c.tickLower,
            c.tickUpper,
            c.liquidity
        );

        ...
    }
```

During unsubscribe, context is built for the position, including the owner:

```solidity
    function _buildContextFromToken(
        uint256 tokenId,
        bool includeOwner
    ) internal view returns (NotifyContext memory ctx) {
        IPositionHandler handler = getHandler(tokenId);

        ...

        if (includeOwner) {
            ctx.owner = handler.ownerOf(tokenId);
        }

    }
```

```solidity
    function ownerOf(uint256 tokenId) external view override returns (address) {
        return IERC721(address(positionManager)).ownerOf(tokenId);
    }
```

Because the transfer already occurred, ownerOf(tokenId) returns the new owner's address.

The unsubscribe function then passes this owner to notifyUnsubscribeWithContext:

```solidity
    function notifyUnsubscribeWithContext(
        bytes32 posKey,
        bytes32 poolIdRaw,
        int24 currentTick,
        address ownerAddr,
        int24 tickLower,
        int24 tickUpper,
        uint128 liquidity
    ) external onlyPositionManagerAdapter {
        ....

        _claimRewards(posKey, ownerAddr);

        _removePosition(pid, posKey);

    }
```

Finally, rewards are transferred:

```solidity
    function _claimRewards(
        bytes32 posKey,
        address recipient
    ) internal returns (uint256 amount) {
        amount = positionRewards[posKey].claim();

        if (amount > 0) {
            BMX.transfer(recipient, amount);

            emit Claimed(recipient, amount);
        }
    }
```

Since recipient is the new owner, the previous LP loses all their accumulated rewards.

## Recommendation

The reward claim logic should be updated to reference the recorded position owner (tracked from subscription) rather than the current NFT owner.

```solidity
    function notifyUnsubscribeWithContext(
        bytes32 posKey,
        bytes32 poolIdRaw,
        int24 currentTick,
        address ownerAddr,
        int24 tickLower,
        int24 tickUpper,
        uint128 liquidity
    ) external onlyPositionManagerAdapter {

        ...

        @ audit Bug
-     _claimRewards(posKey, ownerAddr);

       @ audit Fix

+     address owner = positionOwner[posKey];
+     _claimRewards(posKey, ownerAddr);

    }
```
