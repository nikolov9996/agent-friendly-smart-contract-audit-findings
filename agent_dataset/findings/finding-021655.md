---
id: 21655
severity: "High"
---

# `erc721DecreaseIsolateSupplyOnLiquidate`

## Description

When `isolateLiquidate(supplyAsCollateral=false)` is executed, finally `erc721DecreaseIsolateSupplyOnLiquidate()` will be executed and the NFT will be transferred to the user.

```solidity
function erc721DecreaseIsolateSupplyOnLiquidate(
  DataTypes.AssetData storage assetData,
  uint256[] memory tokenIds
) internal {
  for (uint256 i = 0; i < tokenIds.length; i++) {
    DataTypes.ERC721TokenData storage tokenData = assetData.erc721TokenData[tokenIds[i]];
    require(tokenData.supplyMode == Constants.SUPPLY_MODE_ISOLATE, Errors.INVALID_SUPPLY_MODE);

    assetData.userScaledIsolateSupply[tokenData.owner] -= 1;

    tokenData.owner = address(0);
    tokenData.supplyMode = 0;
    //missing tokenData.lockerAddr = address(0);
  }

  assetData.totalScaledIsolateSupply -= tokenIds.length;
}
```

We know from the above code that this method does not clear the `tokenData.lockerAddr`, so now `tokenData` is:

  * erc721TokenData[NFT_1].owner = 0
  * erc721TokenData[NFT_1].supplyMode = 0
  * erc721TokenData[NFT_1].lockerAddr = `address(poolManager)`

User Alice has NFT_1; then Alice executes `BVault.depositERC721(NFT_1, supplyMode = SUPPLY_MODE_CROSS)` will succeed, `deposit()` does not check `lockerAddr`.

So `tokenData` becomes:

  * erc721TokenData[NFT_1].owner = Alice
  * erc721TokenData[NFT_1].supplyMode = `SUPPLY_MODE_CROSS`
  * erc721TokenData[NFT_1].lockerAddr = `address(poolManager)` - not changed.

After that the user’s NFT_1 will be locked because `withdrawERC721()` `->` `validateWithdrawERC721()` will check that `lockerAddr` must be `address(0)`:

```solidity
function validateWithdrawERC721(
...
  for (uint256 i = 0; i < inputParams.tokenIds.length; i++) {
    DataTypes.ERC721TokenData storage tokenData = VaultLogic.erc721GetTokenData(assetData, inputParams.tokenIds[i]);
    require(tokenData.owner == inputParams.onBehalf, Errors.INVALID_CALLER);
    require(tokenData.supplyMode == inputParams.supplyMode, Errors.INVALID_SUPPLY_MODE);

    require(tokenData.lockerAddr == address(0), Errors.ASSET_ALREADY_LOCKED_IN_USE);
  }
}
```

Other `Isolate` methods cannot be operated either.

Note: `erc721DecreaseIsolateSupply()` is similar.

## Proof of Concept

no poc

## Recommendation

```solidity
function erc721DecreaseIsolateSupplyOnLiquidate(
  DataTypes.AssetData storage assetData,
  uint256[] memory tokenIds
) internal {
  for (uint256 i = 0; i < tokenIds.length; i++) {
    DataTypes.ERC721TokenData storage tokenData = assetData.erc721TokenData[tokenIds[i]];
    require(tokenData.supplyMode == Constants.SUPPLY_MODE_ISOLATE, Errors.INVALID_SUPPLY_MODE);

    assetData.userScaledIsolateSupply[tokenData.owner] -= 1;

    tokenData.owner = address(0);
    tokenData.supplyMode = 0;
    tokenData.lockerAddr = address(0);
  }

  assetData.totalScaledIsolateSupply -= tokenIds.length;
}

function erc721DecreaseIsolateSupply(
  DataTypes.AssetData storage assetData,
  address user,
  uint256[] memory tokenIds
) internal {
  for (uint256 i = 0; i < tokenIds.length; i++) {
    DataTypes.ERC721TokenData storage tokenData = assetData.erc721TokenData[tokenIds[i]];
    require(tokenData.supplyMode == Constants.SUPPLY_MODE_ISOLATE, Errors.INVALID_SUPPLY_MODE);

    tokenData.owner = address(0);
    tokenData.supplyMode = 0;
    tokenData.lockerAddr = address(0);
  }

  assetData.totalScaledIsolateSupply -= tokenIds.length;
  assetData.userScaledIsolateSupply[user] -= tokenIds.length;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑reset omission in the ERC‑721liquidation path of the BVault contract. When an NFT that was supplied in isolate mode is liquidated via isolateLiquidate(supplyAsCollateral=false), the internal function erc721DecreaseIsolateSupplyOnLiquidate iterates over each tokenId, clears the owner field and resets the supplyMode flag, but it fails to clear the lockerAddr field that records which contract is currently holding the token. As a result the tokenData entry ends up with owner set to address(0) and supplyMode cleared, while lockerAddr still points to the pool manager address. Because the lockerAddr is not reset, the token is considered "locked in use" by later validation logic. When the user later tries to deposit the same NFT again (for example in cross‑supply mode) the deposit function does not check lockerAddr, so the token appears to belong to the user and the contract accepts the deposit. However any subsequent withdraw or other isolate‑mode operations invoke validateWithdrawERC721, which requires tokenData.lockerAddr to be address(0). The stale lockerAddr causes the require to revert with ASSET_ALREADY_LOCKED_IN_USE, effectively freezing the NFT. The bug can be triggered for any user who supplies an ERC‑721 token in isolate mode and later experiences liquidation, or who manually calls the isolateLiquidate path. The impact is that the user’s NFT becomes unusable: the UI may show the NFT as owned, but on‑chain checks prevent withdrawal, transfer, or further protocol interactions, leading to a denial‑of‑service style loss of access to the asset. The issue was discovered during a Code4rena audit by inspecting the state updates performed after liquidation and noticing that lockerAddr was never cleared. It is hard to notice because the token is transferred back to the user and no event signals that the lock flag remains set, and the deposit function does not validate the locker address, so the problem only surfaces later when a withdraw is attempted. The proper fix is to reset tokenData.lockerAddr to address(0) in both erc721DecreaseIsolateSupplyOnLiquidate and the related erc721DecreaseIsolateSupply function, and to ensure any other paths that release isolation also clear this field. Optionally, deposit functions should also verify that lockerAddr is zero before accepting a token, providing an additional safety net. This class of bug is an incomplete cleanup of mutable state after a lifecycle transition, leading to stale references that break invariant checks and cause asset lock‑up.
