---
id: 25027
severity: "Crit/High"
---

# Bad debt is never handled which places insolvency risks on BendDAO

## Description



## Proof of Concept

`LiquidationLogic::executeCrossLiquidateERC20()` [allows](<https://github.com/code-423n4/2024-07-benddao/blob/main/src/libraries/logic/LiquidationLogic.sol#L99-L105>) partial, liquidations, so the likely outcome here would be liquidation of the debt corresponding to the available collateral, but some debt could be outstanding. `ERC721` liquidations don't allow partial liquidations in the same way, as the price of each collateral asset is based on the debt value only, so it could happen that these debt assets are not liquidated at all.

As withdrawing deposits depends on the protocol having liquidity, if these assets are borrowed and there is no way to repay them, users will not be able to withdraw.

## Recommendation

On liquidation, place a mechanism to handle the creation of bad debt. This could be implemented as a reserve or by decreasing the supply index or similar, so the bad debt is redistributed by the suppliers.
