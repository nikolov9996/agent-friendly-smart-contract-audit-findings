---
id: 25720
severity: "Crit/High"
---

# state.cumulativeDepositsMultiplierX18 may become 0 or negative, leading to loss of funds

## Description

state.cumulativeDepositsMultiplierX18 may go below 0 if an account is [socialized](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngine.sol#L311-L312>) or in the worst case, 0, which will have greater impact.

The point of socializing a spot account is eliminating the borrowed amount from the short account and transferring it to the other depositors.

The problem is that the multiplier may become 0 or negative which is never handled. If the multiplier goes to 0, every deposit will [revert](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngineState.sol#L128>) and the user will lose its funds.

If it becomes negative, every deposit will be treated as a short instead and the user may be liquidated (deposits have no health check).

## Proof of Concept

No PoC provided.

## Recommendation

Don't let the multiplier become 0 or lower by reverting in this case.
