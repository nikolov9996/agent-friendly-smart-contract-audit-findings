---
id: 13200
severity: "High"
---

# Uninitialized State Index DoS From Reward Activation

## Description

The LEND by TEN Finance protocol provides incentive mechanisms that reward the protocol users. Specifically, the reward mechanism follows the same approach as the COMP reward in Compound. Our analysis on the related LENDt reward in LEND by TEN Finance shows the current logic needs to be improved.
To elaborate, we show below the initial logic of setLendtSpeedInternal() that kicks off the actual minting of protocol tokens. It comes to our attention that the initial supply-side index is configured on the conditions of LendtSupplyState[address(tToken)].index == 0 and LendtSupplyState[address(tToken)].block == 0 (line 4384). However, for an already listed market with a current speed of 0, the first condition is indeed met while the second condition does not! The reason is that both supply-side state and borrow-side state have the associated block information updated, which is diligently performed via other helper pairs updateLendtSupplyIndex()/updateLendtBorrowIndex(). As a result, the setLendtSpeedInternal() logic does not properly set up the default supply-side index and the default borrow-side index.
```solidity
function setLendtSpeedInternal(TToken tToken, uint lendtSpeed) internal {
    uint currentLendtSpeed = lendtSpeeds[address(tToken)];
    if (currentLendtSpeed != 0) {
        // note that LENDt speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: tToken.borrowIndex()});
        updateLendtSupplyIndex(address(tToken));
        updateLendtBorrowIndex(address(tToken), borrowIndex);
    } else if (lendtSpeed != 0) {
        // Add the LENDt market
        Market storage market = markets[address(tToken)];
        require(market.isListed == true, "lendt market is not listed");
        if (lendtSupplyState[address(tToken)].index == 0 && lendtSupplyState[address(tToken)].block == 0) {
            lendtSupplyState[address(tToken)] = LendtMarketState({
                index: lendtInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (lendtBorrowState[address(tToken)].index == 0 && lendtBorrowState[address(tToken)].block == 0) {
            lendtBorrowState[address(tToken)] = LendtMarketState({
                index: lendtInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (currentLendtSpeed != lendtSpeed) {
            lendtSpeeds[address(tToken)] = lendtSpeed;
            emit LendtSpeedUpdated(tToken, lendtSpeed);
        }
    }
}

function updateLendtSupplyIndex(address tToken) internal {
    LendtMarketState storage supplyState = lendtSupplyState[tToken];
    uint supplySpeed = lendtSpeeds[tToken];
    uint blockNumber = getBlockNumber();
    uint deltaBlocks = sub_(blockNumber, uint(supplyState.block));
    if (deltaBlocks > 0 && supplySpeed > 0) {
        uint supplyTokens = TToken(tToken).totalSupply();
        uint lendtAccrued = mul_(deltaBlocks, supplySpeed);
        Double memory ratio = supplyTokens > 0 ? fraction(lendtAccrued, supplyTokens) : Double({mantissa: 0});
        Double memory index = add_(Double({mantissa: supplyState.index}), ratio);
        lendtSupplyState[tToken] = LendtMarketState({
            index: safe224(index.mantissa, "new index exceeds bits"),
            block: safe32(blockNumber, "block number exceeds 32 bits")
        });
    } else if (deltaBlocks > 0) {
        supplyState.block = safe32(blockNumber, "block number exceeds 32 bits");
    }
}
```
When the reward speed is configured, since the supply-side and borrow-side state indexes are not initialized, any normal functionality such as mint() will be immediately reverted! This revert occurs inside the distributeSupplierLendt()/distributeBorrowerLendt() functions. Using the distributeSupplierLendt() function as an example, the revert is caused from the arithmetic operation sub_(supplyIndex, supplierIndex) (line 4466). Since the supplyIndex is not properly initialized, it will be updated to a smaller number from an earlier invocation of updateLendtSupplyIndex() (lines 4376-4378). However, when the distributeSupplierLendt() function is invoked, the supplierIndex is reset with LendtInitialIndex (line 4463), which unfortunately reverts the arithmetic operation sub_(supplyIndex, supplierIndex)!
```solidity
function distributeSupplierLendt(address tToken, address supplier) internal {
    LendtMarketState storage supplyState = lendtSupplyState[tToken];
    Double memory supplyIndex = Double({mantissa: supplyState.index});
    Double memory supplierIndex = Double({mantissa: lendtSupplierIndex[tToken][supplier]});
    lendtSupplierIndex[tToken][supplier] = supplyIndex.mantissa;
    if (supplierIndex.mantissa == 0 && supplyIndex.mantissa > 0) {
        supplierIndex.mantissa = lendtInitialIndex;
        Double memory deltaIndex = sub_(supplyIndex, supplierIndex);
        uint supplierTokens = TToken(tToken).balanceOf(supplier);
        uint supplierDelta = mul_(supplierTokens, deltaIndex);
        uint supplierAccrued = add_(lendtAccrued[supplier], supplierDelta);
        lendtAccrued[supplier] = supplierAccrued;
        emit DistributedSupplierLendt(TToken(tToken), supplier, supplierDelta, supplyIndex.mantissa);
    }
}
```

## Proof of Concept

no poc

## Recommendation

Properly initialize the reward state indexes in the above affected setLendtSpeedInternal() function. An example revision is shown as follows:
```solidity
function setLendtSpeedInternal(TToken tToken, uint lendtSpeed) internal {
    uint currentLendtSpeed = lendtSpeeds[address(tToken)];
    if (currentLendtSpeed != 0) {
        // note that Lendt speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: tToken.borrowIndex()});
        updateLendtSupplyIndex(address(tToken));
        updateLendtBorrowIndex(address(tToken), borrowIndex);
    } else if (lendtSpeed != 0) {
        // Add the Lendt market
        Market storage market = markets[address(tToken)];
        require(market.isListed == true, "lendt market is not listed");
        if (lendtSupplyState[address(tToken)].index == 0) {
            lendtSupplyState[address(tToken)] = LendtMarketState({
                index: lendtInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (lendtBorrowState[address(tToken)].index == 0) {
            lendtBorrowState[address(tToken)] = LendtMarketState({
                index: lendtInitialIndex,
                block: safe32(getBlockNumber(), "block number exceeds 32 bits")
            });
        }
        if (currentLendtSpeed != lendtSpeed) {
            lendtSpeeds[address(tToken)] = lendtSpeed;
            emit LendtSpeedUpdated(tToken, lendtSpeed);
        }
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition caused by uninitialized reward state indexes in the LEND by TEN Finance protocol’s LENDt incentive system. The contract stores a supply‑side and a borrow‑side market state, each containing an index and the block number at which the index was last updated. When a market is already listed and its reward speed has previously been set to zero, the helper functions that update the block numbers are still called, so the block field becomes non‑zero while the index field remains zero. The setLendtSpeedInternal function only creates the default index when both the index and the block are zero, therefore the index is never initialized in this scenario. Later, any operation that distributes rewards – for example a mint that triggers distributeSupplierLendt – reads the uninitialized supply index, compares it with a supplier‑specific index that is reset to the protocol’s initial index, and performs a subtraction. Because the stored supply index is still zero (or a stale smaller value), the subtraction underflows and the transaction reverts. As a result, normal user actions such as minting, borrowing or repaying are blocked, effectively freezing the market and preventing users from receiving or withdrawing funds. The issue appears only when the reward speed is changed from zero to a non‑zero value on an already active market, which can be missed by standard testing that only covers fresh market deployment. It was discovered during a manual audit that examined the logic of setLendtSpeedInternal and the reward distribution functions. The bug is hard to notice because the condition that checks both index and block being zero looks innocuous, yet it fails to account for the block being updated independently. To remediate the problem, the initialization logic should set the index whenever the index field is zero, regardless of the block value, ensuring that both supply‑side and borrow‑side indexes are always defined before any reward distribution occurs. This change restores the expected behavior where users receive correct LENDt rewards and can continue to interact with the market without unexpected reverts.
