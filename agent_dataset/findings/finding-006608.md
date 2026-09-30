---
id: 6608
severity: "High"
---

# ATokenERC6909.totalSupply for debt tokens uses the liquidity index

## Description

The totalSupply function is defined as:
```solidity
function totalSupply(uint256 id) public view override returns (uint256) {
    uint256 currentSupplyScaled = super.totalSupply(id);
    if (currentSupplyScaled == 0) {
        return 0;
    }
    return currentSupplyScaled.rayMul(
        POOL.getReserveNormalizedIncome(_underlyingAssetAddresses[id])
    );
}
```
which assumes the id provided is always an aToken id and thus uses the POOL.getReserveNormalizedIncome(_underlyingAssetAddresses[id]) as an index.
1. This function needs to be used by other on and off chain agent to query the correct amount for debt tokens as well.
2. It is used in MiniPoolPiReserveInterestRateStrategy.getCurrentInterestRates() to calculate the utilisation rate, and so wrong values are returned.
3. It is used in _afterTokenTransfer to supply the oldSupply to INCENTIVES_CONTROLLER. And thus for debt tokens with incentives incorrect values would be provided.
Fortunately enough the correct value of totalVariableDebt was calculated manually in MiniPoolReserveLogic.updateInterestRates and thus the state transition for both the default and PiReserve InterestRateStrategys use the correct calculation:
```solidity
vars.totalVariableDebt = IAERC6909(reserve.aTokenAddress).scaledTotalSupply(
    (reserve.variableDebtTokenID)
).rayMul(reserve.variableBorrowIndex)
```
If the above optimisation would have not been used the issue would have been more severe.

## Proof of Concept

no poc

## Recommendation

Make sure totalSupply checks whether the id is an aToken or debtToken:
```solidity
/**
* @notice Gets the total supply for a token ID.
* @param id The token ID.
* @return The total supply scaled by normalized income/debt.
*/
function totalSupply(uint256 id) public view override returns (uint256) {
    uint256 currentSupplyScaled = super.totalSupply(id);
    if (currentSupplyScaled == 0) {
        return 0;
    }
    uint256 index = 0;
    if (isDebtToken(id)) {
        index = POOL.getReserveNormalizedVariableDebt(_underlyingAssetAddresses[id]);
    } else {
        index = POOL.getReserveNormalizedIncome(_underlyingAssetAddresses[id]);
    }
    return currentSupplyScaled.rayMul(index);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the totalSupply function of the ERC‑6909 token implementation used by the protocol. The function retrieves the scaled total supply from the parent contract and then multiplies it by a pool index that is obtained via POOL.getReserveNormalizedIncome. This logic assumes that the supplied token identifier always corresponds to an aToken, which represents supplied assets. However, the same function is also called for debt tokens (variable debt tokens) where the correct index should be the normalized variable debt index obtained from POOL.getReserveNormalizedVariableDebt. Because the function does not distinguish between aToken and debt token identifiers, it applies the income index to debt token supplies. The root cause is a missing type check that would select the appropriate index based on the token class. When a debt token identifier is passed, the function returns a value that is inflated or deflated depending on the relationship between the income index and the variable debt index. This incorrect totalSupply value propagates to several critical calculations: the utilisation rate used by MiniPoolPiReserveInterestRateStrategy, the oldSupply parameter supplied to the incentives controller in _afterTokenTransfer, and any off‑chain or on‑chain agents that query totalSupply for debt token balances. From a user perspective the symptoms may appear as a mismatch between the displayed variable debt amount and the actual borrowed amount, unexpected zero or unusually high utilisation rates, and incentives that seem to be allocated incorrectly. The issue is subtle because the function still returns a non‑zero number, so a simple sanity check does not reveal the problem; only a deeper audit of the index selection logic uncovers the mismatch. The bug violates the protocol’s accounting assumptions that totalSupply for each token type is scaled by its respective index, leading to inaccurate interest‑rate calculations and potentially mis‑distributed rewards. The flaw was discovered during a security review where the auditor compared the totalSupply implementation against the expected behaviour for debt tokens. To remediate, the totalSupply function must first determine whether the supplied id corresponds to a debt token or an aToken and then apply the correct pool index – POOL.getReserveNormalizedVariableDebt for debt tokens and POOL.getReserveNormalizedIncome for aTokens – before performing the ray multiplication. This change restores correct accounting for both token classes and prevents downstream miscalculations.
