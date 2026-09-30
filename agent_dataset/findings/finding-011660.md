---
id: 11660
severity: "High"
---

# Uninitialized State Index DoS From Reward Activation

## Description

The Atlantis protocol is in essence an over-collateralized lending pool that has the lending functionality and supports a number of normal lending functionalities for supplying and borrowing users, i.e., mint()/redeem() and borrow()/repay(). In the following, we examine the rewarding logic of the protocol token, i.e., Atlantis (ATL).

To elaborate, we show below the initial logic of setAtlantisSpeedInternal() that kicks off the actual minting of protocol tokens. It comes to our attention that the initial supply-side index is configured on the conditions of atlantisSupplyState[address(aToken)].index == 0 and atlantisSupplyState[address(aToken)].block == 0 (line 1088). However, for an already listed market with a current speed of 0, the first condition is indeed met while the second condition does not! The reason is that both supply-side state and borrow-side state have the associated block information updated, which is diligently performed via other helper pairs updateAtlantisSupplyIndex()/updateAtlantisBorrowIndex(). As a result, the setAtlantisSpeedInternal() logic does not properly set up the default supply-side index and the default borrow-side index.

```solidity
function setAtlantisSpeedInternal(AToken aToken, uint atlantisSpeed) internal {
    uint currentAtlantisSpeed = atlantisSpeeds[address(aToken)];
    if (currentAtlantisSpeed != 0) {
        // note that Atlantis speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: aToken.borrowIndex()});
        updateAtlantisSupplyIndex(address(aToken));
        updateAtlantisBorrowIndex(address(aToken), borrowIndex);
    } else if (atlantisSpeed != 0) {
        // Add the Atlantis market
        Market storage market = markets[address(aToken)];
        require(market.isListed == true, "atlantis market is not listed");
        if (atlantisSupplyState[address(aToken)].index == 0 && atlantisSupplyState[address(aToken)].block == 0) {
            atlantisSupplyState[address(aToken)] = AtlantisMarketState({
                index: atlantisInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (atlantisBorrowState[address(aToken)].index == 0 && atlantisBorrowState[address(aToken)].block == 0) {
            atlantisBorrowState[address(aToken)] = AtlantisMarketState({
                index: atlantisInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (currentAtlantisSpeed != atlantisSpeed) {
            atlantisSpeeds[address(aToken)] = atlantisSpeed;
            emit AtlantisSpeedUpdated(aToken, atlantisSpeed);
        }
    }
}

function updateAtlantisSupplyIndex(address aToken) internal {
    AtlantisMarketState storage supplyState = atlantisSupplyState[aToken];
    uint supplySpeed = atlantisSpeeds[aToken];
    uint blockNumber = getBlockNumber();
    uint deltaBlocks = sub_(blockNumber, uint(supplyState.block));
    if (deltaBlocks > 0 && supplySpeed > 0) {
        uint supplyTokens = AToken(aToken).totalSupply();
        uint atlantisAccrued = mul_(deltaBlocks, supplySpeed);
        Double memory ratio = supplyTokens > 0 ? fraction(atlantisAccrued, supplyTokens) : Double({mantissa: 0});
        Double memory index = add_(Double({mantissa: supplyState.index}), ratio);
        atlantisSupplyState[aToken] = AtlantisMarketState({
            index: safe224(index.mantissa, "new index exceeds bits"),
            block: safe32(blockNumber, "block number exceeds 32 bits")
        });
    } else if (deltaBlocks > 0) {
        supplyState.block = safe32(blockNumber, "block number exceeds 32 bits");
    }
}
```

When the reward speed is configured, since the supply-side and borrow-side state indexes are not initialized, any normal functionality such as mint() will be immediately reverted! This revert occurs inside the distributeSupplierAtlantis()/distributeBorrowerAtlantis() functions. Using the distributeSupplierAtlantis() function as an example, the revert is caused from the arithmetic operation sub_(supplyIndex, supplierIndex) (line 1174). Since the supplyIndex is not properly initialized, it will be updated to a smaller number from an earlier invocation of updateAtlantisSupplyIndex() (lines 1123-1126). However, when the distributeSupplierAtlantis() function is invoked, the supplierIndex is reset with atlantisInitialIndex (line 1171), which unfortunately reverts the arithmetic operation sub_(supplyIndex, supplierIndex)!

```solidity
function distributeSupplierAtlantis(address aToken, address supplier) internal {
    if (vaults.length != 0) {
        releaseToVault();
    }
    AtlantisMarketState storage supplyState = atlantisSupplyState[aToken];
    Double memory supplyIndex = Double({mantissa: supplyState.index});
    Double memory supplierIndex = Double({mantissa: atlantisSupplierIndex[aToken][supplier]});
    atlantisSupplierIndex[aToken][supplier] = supplyIndex.mantissa;
    if (supplierIndex.mantissa == 0 && supplyIndex.mantissa > 0) {
        supplierIndex.mantissa = atlantisInitialIndex;
        Double memory deltaIndex = sub_(supplyIndex, supplierIndex);
        uint supplierTokens = AToken(aToken).balanceOf(supplier);
        uint supplierDelta = mul_(supplierTokens, deltaIndex);
        uint supplierAccrued = add_(atlantisAccrued[supplier], supplierDelta);
        atlantisAccrued[supplier] = supplierAccrued;
        emit DistributedSupplierAtlantis(AToken(aToken), supplier, supplierDelta, supplyIndex.mantissa);
    }
}
```

## Proof of Concept

no poc

## Recommendation

Properly initialize the reward state indexes in the above affected setAtlantisSpeedInternal() function. An example revision is shown as follows:

```solidity
function setAtlantisSpeedInternal(AToken aToken, uint atlantisSpeed) internal {
    uint currentAtlantisSpeed = atlantisSpeeds[address(aToken)];
    if (currentAtlantisSpeed != 0) {
        // note that Atlantis speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: aToken.borrowIndex()});
        updateAtlantisSupplyIndex(address(aToken));
        updateAtlantisBorrowIndex(address(aToken), borrowIndex);
    } else if (atlantisSpeed != 0) {
        // Add the Atlantis market
        Market storage market = markets[address(aToken)];
        require(market.isListed == true, "atlantis market is not listed");
        if (atlantisSupplyState[address(aToken)].index == 0) {
            atlantisSupplyState[address(aToken)].index = atlantisInitialIndex;
            atlantisSupplyState[address(aToken)].block = safe32(getBlockNumber());
        }
        if (atlantisBorrowState[address(aToken)].index == 0) {
            atlantisBorrowState[address(aToken)].index = atlantisInitialIndex;
            atlantisBorrowState[address(aToken)].block = safe32(getBlockNumber());
        }
        if (currentAtlantisSpeed != atlantisSpeed) {
            atlantisSpeeds[address(aToken)] = atlantisSpeed;
            emit AtlantisSpeedUpdated(aToken, atlantisSpeed);
        }
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition caused by uninitialized reward state indexes in the Atlantis protocol’s liquidity‑reward module. When a market is already listed and its Atlantis reward speed has previously been set to zero, the function that adds the market (setAtlantisSpeedInternal) checks both the index and the block number before initializing the supply‑side and borrow‑side states. Because the block field is already populated by earlier calls to updateAtlantisSupplyIndex or updateAtlantisBorrowIndex, the second part of the condition (block == 0) fails, leaving the index at its default value of zero. Later, when a user performs a normal operation such as mint() or redeem(), the protocol attempts to distribute rewards through distributeSupplierAtlantis (or its borrow counterpart). This function reads the current supply index, which is now a stale or smaller value, and subtracts the supplier’s stored index that has been reset to the constant atlantisInitialIndex. The subtraction sub_(supplyIndex, supplierIndex) under these circumstances triggers an arithmetic error that reverts the transaction. As a result, any action that triggers reward distribution – typically supply, borrow, repay or redemption – fails immediately, effectively freezing user interactions with the affected market. The impact is that lenders and borrowers cannot move their funds, balances appear unchanged, and the protocol’s revenue stream from Atlantis rewards stops, while the funds already supplied remain locked in the contract. The condition occurs only when the reward speed is changed from zero to a non‑zero value on a market whose block number has already been recorded, which is a subtle state‑initialization bug that is easy to miss during testing because the index appears to be zero only in storage, not in the visible UI. The issue was discovered during a manual audit of the reward‑distribution logic, where the auditor noticed that the initialization guard required both index and block to be zero. The bug is hard to notice because the contract does not emit a specific error message for the revert; users simply see a generic transaction failure. The proper fix is to initialize the index independently of the block field – for example, setting the index to atlantisInitialIndex whenever the index is zero, regardless of the block value – and to ensure that both supply and borrow states are correctly populated before any reward distribution is attempted. This change restores the expected behavior where users supply assets and receive rewards without unexpected reverts, aligning the contract’s accounting with its business logic that rewards should be accrued only after proper state initialization.
