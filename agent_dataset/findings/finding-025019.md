---
id: 25019
severity: "Medium"
---

# Protected downside is not updated when cds.getTotalCdsDepositedAmount() < downsideProtected

## Description



## Proof of Concept

## Impact

1. A condition arrives for a user where the downside protection of the user is greater than total CDS deposited Amount.
2. The user calls `CDS::withdraw`, where the downside protection shortfall is fulfilled via layer zero call.
3. However, due to no downside protection update, the cumulative value will get artificially inflated, allowing CDS withdrawers gain higher option fees than intended

## Recommendation

It is recommended to update downside protection for the amount not borrowed from other chain

```diff
    function _getDownsideFromCDS(
        uint128 downsideProtected,
        uint256 feeForOFT
    ) internal {
        if (cds.getTotalCdsDepositedAmount() < downsideProtected) {
            // Call the oftOrCollateralReceiveFromOtherChains function in global variables
+         cds.updateDownsideProtected(downsideProtected);
            globalVariables.oftOrCollateralReceiveFromOtherChains{value: feeForOFT}(
                IGlobalVariables.FunctionToDo(3),
                IGlobalVariables.USDaOftTransferData(address(treasury),downsideProtected - cds.getTotalCdsDepositedAmount()),
                // Since we don't need ETH, we have passed zero params
                IGlobalVariables.CollateralTokenTransferData(address(0),0,0,0),
                IGlobalVariables.CallingFunction.BORROW_WITHDRAW,
                msg.sender
            );
        } else {
            // updating downside protected from this chain in CDS
            cds.updateDownsideProtected(downsideProtected);
        }
        // Burn the borrow amount
        treasury.approveTokens(IBorrowing.AssetName.USDa, address(this), downsideProtected);
        bool success = usda.contractBurnFrom(address(treasury), downsideProtected);
        if (!success) revert Borrow_BurnFailed();
    }
```
