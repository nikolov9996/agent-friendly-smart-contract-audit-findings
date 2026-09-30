---
id: 10101
severity: "High"
---

# Impossible to add/remove liquidity if numTokens < MAX_NUM_TOKENS

## Description

```solidity
function addLiquidity(
    uint256[MAX_NUM_TOKENS] calldata amounts_,
    uint256 minLpAmount_,
    address receiver_
external
nonReentrant
returns (uint256)
```
Here it required _amount to be provided with the length of 32. On the other hand, later it requires a different thing:
```solidity
if (amounts_.length != _numTokens) revert Pool__InvalidParams();
```
So, these two requirements conflict when we have _numTokens below 32. Thus, it is impossible to provide liquidity for such pools. Same thing for removeLiquidity().

## Proof of Concept

No poc.

## Recommendation

Consider changing to:
```solidity
function addLiquidity(
    uint256[] calldata amounts_,
    uint256 minLpAmount_,
    address receiver_
external
nonReentrant
returns (uint256)
```
The same thing should be fixed for removeLiquidity().

## Derived Narrative

The following field is derived content and may not be source-grounded:

Thecontract defines the addLiquidity and removeLiquidity functions to accept a calldata array of type uint256[MAX_NUM_TOKENS], where MAX_NUM_TOKENS is a constant equal to 32. Immediately after the calldata is received the code checks that the length of the supplied array matches the runtime variable _numTokens, which represents the actual number of tokens in the pool. When a pool is configured with fewer than 32 tokens, the static array still has a fixed length of 32, but the length check expects a smaller value, causing the condition amounts_.length != _numTokens to evaluate to true and the transaction to revert with Pool__InvalidParams. This mismatch creates a logical inconsistency: the function signature enforces a maximum‑size fixed array while the business rule enforces a variable‑size requirement. As a result, users are unable to add or remove liquidity for any pool whose token count is below the maximum, effectively denying service to those pools. The impact is that legitimate liquidity providers cannot deposit assets, balances remain unchanged, and the protocol cannot support smaller pools, potentially reducing market depth and revenue. The issue is discovered during a manual audit that compared the function signature against the runtime validation logic. It is subtle because the Solidity compiler accepts a fixed‑size calldata array without warnings, and the revert only occurs at execution time when a user attempts the operation, making it easy to miss in basic testing. The vulnerability belongs to the class of input‑validation mismatches and API contract violations, where the declared interface does not align with internal invariants. To fix the problem the function should accept a dynamic calldata array (uint256[] calldata) and the length check should be retained, ensuring that the caller can supply exactly _numTokens entries regardless of the pool size. This change restores the intended business logic that the amount array length must equal the number of tokens, allowing liquidity operations for any pool size and eliminating the denial‑of‑service condition.
