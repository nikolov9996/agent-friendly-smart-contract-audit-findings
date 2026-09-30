---
id: 12699
severity: "High"
---

# Uninitialized State Index DoS From Reward Activation

## Description

```solidity
function setCompSpeedInternal(CToken cToken, uint compSpeed) internal {
    uint currentCompSpeed = compSpeeds[address(cToken)];
    if (currentCompSpeed != 0) {
        // note that COMP speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: cToken.borrowIndex()});
        updateCompSupplyIndex(address(cToken));
        updateCompBorrowIndex(address(cToken), borrowIndex);
    } else if (compSpeed != 0) {
        // Add the COMP market
        Market storage market = markets[address(cToken)];
        require(market.isListed == true, "CMktNtL"); // comp market is not listed
        if (compSupplyState[address(cToken)].index == 0 && compSupplyState[address(cToken)].block == 0) {
            compSupplyState[address(cToken)] = CompMarketState({
                index: compInitialIndex,
                block: safe32(getBlockNumber(), "B#Ex") // block number exceeds bits
            });
        }
        if (compBorrowState[address(cToken)].index == 0 && compBorrowState[address(cToken)].block == 0) {
            compBorrowState[address(cToken)] = CompMarketState({
                index: compInitialIndex,
                block: safe32(getBlockNumber(), "B#Ex") // block number exceeds bits
            });
        }
        if (currentCompSpeed != compSpeed) {
            compSpeeds[address(cToken)] = compSpeed;
            emit CompSpeedUpdated(cToken, compSpeed);
        }
    }
}

function updateCompSupplyIndex(address cToken) internal {
    CompMarketState storage supplyState = compSupplyState[cToken];
    uint supplySpeed = compSpeeds[cToken];
    uint blockNumber = getBlockNumber();
    uint deltaBlocks = sub_(blockNumber, uint(supplyState.block));
    if (deltaBlocks > 0 && supplySpeed > 0) {
        uint supplyTokens = CToken(cToken).totalSupply();
        uint compAccrued = mul_(deltaBlocks, supplySpeed);
        Double memory ratio = supplyTokens > 0 ? fraction(compAccrued, supplyTokens) : Double({mantissa: 0});
        Double memory index = add_(Double({mantissa: supplyState.index}), ratio);
        compSupplyState[cToken] = CompMarketState({
            index: safe224(index.mantissa, "NIdxEx"), // new index exceeds bits
            block: safe32(blockNumber, "B#Ex") // block number exceeds 32 bits
        });
    } else if (deltaBlocks > 0) {
        supplyState.block = safe32(blockNumber, "B#Ex"); // block number exceeds bits
    }
}
```
When the reward speed is configured, since the supply-side and borrow-side state indexes are not initialized, any normal functionality such as mint() will be immediately reverted! This revert occurs inside the distributeSupplierComp()/distributeBorrowerComp() functions. Using the distributeSupplierComp() function as an example, the revert is caused from the arithmetic operation sub_(supplyIndex, supplierIndex) (line 1172). Since the supplyIndex is not properly initialized, it will be updated to a smaller number from an earlier invocation of updateCompSupplyIndex() (lines 1126-1127). However, when the distributeSupplierComp() function is invoked, the supplierIndex is reset with compInitialIndex (line 1169), which unfortunately reverts the arithmetic operation sub_(supplyIndex, supplierIndex)!
```solidity
function distributeSupplierComp(address cToken, address supplier) internal {
    CompMarketState storage supplyState = compSupplyState[cToken];
    Double memory supplyIndex = Double({mantissa: supplyState.index});
    Double memory supplierIndex = Double({mantissa: compSupplierIndex[cToken][supplier]});
    compSupplierIndex[cToken][supplier] = supplyIndex.mantissa;
    if (supplierIndex.mantissa == 0 && supplyIndex.mantissa > 0) {
        supplierIndex.mantissa = compInitialIndex;
    }
    Double memory deltaIndex = sub_(supplyIndex, supplierIndex);
    uint supplierTokens = CToken(cToken).balanceOf(supplier);
    uint supplierDelta = mul_(supplierTokens, deltaIndex);
    uint supplierAccrued = add_(compAccrued[supplier], supplierDelta);
    compAccrued[supplier] = supplierAccrued;
    emit DistributedSupplierComp(CToken(cToken), supplier, supplierDelta, supplyIndex.mantissa);
}
```

## Proof of Concept

no poc

## Recommendation

```solidity
function setCompSpeedInternal(CToken cToken, uint compSpeed) internal {
    uint currentCompSpeed = compSpeeds[address(cToken)];
    if (currentCompSpeed != 0) {
        // note that COMP speed could be set to 0 to halt liquidity rewards for a market
        Exp memory borrowIndex = Exp({mantissa: cToken.borrowIndex()});
        updateCompSupplyIndex(address(cToken));
        updateCompBorrowIndex(address(cToken), borrowIndex);
    } else if (compSpeed != 0) {
        // Add the COMP market
        Market storage market = markets[address(cToken)];
        require(market.isListed == true, "CMktNtL"); // comp market is not listed
        if (compSupplyState[address(cToken)].index == 0) {
            compSupplyState[address(cToken)] = CompMarketState({
                index: compInitialIndex,
                block: safe32(getBlockNumber(), "B#Ex") // block number exceeds bits
            });
        }
        if (compBorrowState[address(cToken)].index == 0) {
            compBorrowState[address(cToken)] = CompMarketState({
                index: compInitialIndex,
                block: safe32(getBlockNumber(), "B#Ex") // block number exceeds bits
            });
        }
        if (currentCompSpeed != compSpeed) {
            compSpeeds[address(cToken)] = compSpeed;
            emit CompSpeedUpdated(cToken, compSpeed);
        }
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that occurs when the reward speed for a market is activated but the internal accounting indexes for supply and borrow side rewards are not properly initialized. The contract stores a CompMarketState for each market, containing an index and the block number at which the index was last updated. In the function that sets the reward speed, the code only creates a new CompMarketState when both the index and the block are zero. When the reward speed changes from zero to a non‑zero value, the indexes may remain at their default value (zero) while the block number is set, or the opposite, leaving the index uninitialized. Later, when a user performs a normal operation such as mint, redeem, borrow or repay, the protocol calls distributeSupplierComp or distributeBorrowerComp to allocate COMP rewards. These functions read the current supply index from compSupplyState and compare it with the supplier’s stored index. Because the supply index is still zero, the subtraction sub_(supplyIndex, supplierIndex) underflows – the supplier index has been reset to the constant compInitialIndex, which is a large positive number. The underflow triggers a revert, causing the whole user transaction to fail. From the user’s perspective the UI shows a transaction that reverts immediately, often with no explicit error message, and the expected balance update (e.g., minted tokens) never occurs, leading to the impression that “my funds disappear” or “the mint fails for no reason”. The impact is that any interaction with the affected market becomes impossible after rewards are turned on, effectively freezing user activity and halting the protocol’s core functionality for that market. The condition is triggered only after the reward speed is set to a non‑zero value and the first user action that invokes reward distribution, making it easy to miss during normal testing because the contract works correctly before rewards are enabled. The issue was discovered during a security audit by Peckshield, which examined the reward‑distribution logic and identified the missing initialization guard. It is hard to notice because the revert originates from an internal arithmetic check rather than a direct require statement, and the error surface is a generic transaction failure. The bug belongs to the class of uninitialized state variable or under‑initialized accounting index vulnerabilities that lead to arithmetic underflow and denial‑of‑service. The correct mitigation is to ensure that when a market is added to the reward program, the compSupplyState and compBorrowState indexes are explicitly set to the protocol‑wide initial index (compInitialIndex) regardless of the block number, and to add safety checks that prevent subtraction when the current index is lower than the stored supplier or borrower index. By initializing the indexes properly, the distribution functions will compute a non‑negative delta, the transaction will succeed, and users will receive the expected token balances and reward accruals.
