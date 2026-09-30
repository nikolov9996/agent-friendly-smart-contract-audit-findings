---
id: 10079
severity: "High"
---

# Incorrect parameters bricks certain functions

## Description

In solidity, if a function parameter list has an array of defined length, it forces the user to pass an array of that length. The call reverts if the passed array is of an unexpected length. This is the case in the setWeightBands and setRamp functions.
```solidity
function setWeightBands(
    uint256[MAX_NUM_TOKENS] calldata tokens_,
    uint256[MAX_NUM_TOKENS] calldata lower_,
    uint256[MAX_NUM_TOKENS] calldata upper_
```
Since MAX_NUM_TOKENS=32, this forces the caller to pass in an array with 32 elements. Any lower and this call reverts. This is also present in the setRamp function.
```solidity
function setRamp(
    uint256 amplification_,
    uint256[MAX_NUM_TOKENS] calldata weights_,
    uint256 duration_,
    uint256 start_
```
However, these functions expect arrays only of the size numTokens. In fact, if a larger array is passed, it will revert due to another line.
```solidity
for (uint256 t = 0; t < MAX_NUM_TOKENS; t++) {
    //...
    if (t >= _numTokens) revert Pool__IndexOutOfBounds();
```
So users are forced to pass in 32-length arrays or the call reverts, and if they do so, the call will still revert since _numTokens will be exceeded if the pool does not actually use 32 tokens. So all calls to both these functions will revert. Thus these functions are unusable.

## Proof of Concept

No poc.

## Recommendation

Remove the size requirement from the function parameters.
```solidity
function setWeightBands(
    uint256[] calldata tokens_,
    uint256[] calldata lower_,
    uint256[] calldata upper_
```
```solidity
function setRamp(
    uint256 amplification_,
    uint256[] calldata weights_,
    uint256 duration_,
    uint256 start_
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the contract's public configuration functions that accept fixed‑size array parameters. In Solidity, declaring a parameter as uint256[MAX_NUM_TOKENS] calldata forces the caller to supply an array whose length exactly matches the constant MAX_NUM_TOKENS, which is set to 32. The functions in question – the one that sets weight bands and the one that sets a ramp – are intended to work with a variable number of tokens defined by the pool’s internal _numTokens value. However, the implementation first checks each index against _numTokens inside a loop and reverts with Pool__IndexOutOfBounds when the loop index exceeds the actual number of tokens. Consequently, two contradictory requirements are imposed: the caller must provide a 32‑element array, yet the contract will reject any element whose index is greater than or equal to _numTokens. If the pool uses fewer than 32 tokens, which is the normal case, any call to these functions will inevitably hit the internal bounds check and revert, even when the caller supplies a correctly sized 32‑element array. This makes the functions effectively unusable. The issue was discovered during a manual audit that examined the function signatures and the subsequent loop logic, revealing the mismatch between the external API contract and the internal accounting. It can be hard to notice because the compiler does not warn about the logical inconsistency; the function signatures appear syntactically correct, and the revert only occurs at runtime when the internal check is hit. From a user’s perspective, attempts to configure weight bands or ramp parameters result in immediate transaction failures with no state change, leading to confusion such as “my transaction reverts even though I passed valid values” or “the UI button does nothing”. The impact is that the protocol cannot be properly configured after deployment, potentially preventing the pool from operating as intended and forcing administrators to abandon or redeploy the contract. The bug belongs to the class of API contract violations where fixed‑size array parameters are used in contexts that require dynamic sizing, causing argument validation failures. The recommended remediation is to replace the fixed‑size array types with dynamic calldata arrays (uint256[] calldata) so that the caller can supply exactly the number of elements required by the pool, eliminating the contradictory length requirement and allowing the internal bounds check to succeed.
