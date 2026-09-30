---
id: 22260
severity: "High"
---

# Misconfigured index boundaries prevent certain swaps in QuantAMMWeightedPool

## Description

Balancer pools can handle up to 8 tokens in weighted pools. QuantAMM uses this feature but optimizes storage by using only two slots. As a result, the first four tokens and the last four tokens are treated separately.

For swaps, this logic is implemented in [`QuantAMMWeightedPool::onSwap`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L242-L265):

```solidity
// if both tokens are within the first storage element
if (request.indexIn < 4 && request.indexOut < 4) {
    QuantAMMNormalisedTokenPair memory tokenWeights = _getNormalisedWeightPair(
        request.indexIn,
        request.indexOut,
        timeSinceLastUpdate,
        totalTokens
    );
    tokenInWeight = tokenWeights.firstTokenWeight;
    tokenOutWeight = tokenWeights.secondTokenWeight;
} else if (request.indexIn > 4 && request.indexOut < 4) {
    // if the tokens are in different storage elements
    QuantAMMNormalisedTokenPair memory tokenWeights = _getNormalisedWeightPair(
        request.indexOut,
        request.indexIn,
        timeSinceLastUpdate,
        totalTokens
    );
    tokenInWeight = tokenWeights.firstTokenWeight;
    tokenOutWeight = tokenWeights.secondTokenWeight;
} else {
    tokenInWeight = _getNormalizedWeight(request.indexIn, timeSinceLastUpdate, totalTokens);
    tokenOutWeight = _getNormalizedWeight(request.indexOut, timeSinceLastUpdate, totalTokens);
}
```

The issue arises in the second `else if` block, which is intended to handle cases where both tokens are in the second slot. However, the condition `request.indexOut < 4` is incorrect; it should be `request.indexOut >= 4`. Consequently, in [`_getNormalisedWeightPair`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L305-L325), the code will revert:

```solidity
function _getNormalisedWeightPair(
    uint256 tokenIndexOne, // @audit indexOut
    uint256 tokenIndexTwo, // @audit indexIn
    // ...
) internal view virtual returns (QuantAMMNormalisedTokenPair memory) {
    uint256 firstTokenIndex = tokenIndexOne; // @audit indexOut
    uint256 secondTokenIndex = tokenIndexTwo; // @audit indexIn
    // ...
    if (tokenIndexTwo > 4) { // @audit indexIn will always be > 4 from the branch above
        firstTokenIndex = tokenIndexOne - 4; // @audit indexOut, must be < 4 hence underflow
        secondTokenIndex = tokenIndexTwo - 4;
        totalTokensInPacked -= 4;
        targetWrappedToken = _normalizedSecondFourWeights;
    } else {
```

Here, `tokenIndexOne - 4` will underflow due to the incorrect condition.

In [`QuantAMMWeightedPool::_getNormalizedWeight`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L370-L404), there is a similar issue where the condition `tokenIndex > 4` should be `tokenIndex >= 4`:

```solidity
if (tokenIndex > 4) { // @audit should be >=
    // get the index in the second storage element
    index = tokenIndex - 4;
    targetWrappedToken = _normalizedSecondFourWeights;
    tokenIndexInPacked -= 4;
} else {
    // @audit first slot
    if (totalTokens > 4) {
         tokenIndexInPacked = 4;
    }
    targetWrappedToken = _normalizedFirstFourWeights;
```

This causes a failure when fetching the multiplier in [`QuantAMMWeightedPool::_calculateCurrentBlockWeight`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L352-L368):

```solidity
int256 blockMultiplier = tokenWeights[tokenIndex + (tokensInTokenWeights)];
```

In this case, `tokenWeights` contains 8 entries, but `tokenIndex + (tokensInTokenWeights)` equals 8, causing an array out-of-bounds error.

The same issue is also present in the following locations, though they currently have no impact:

- In [`QuantAMMWeightedPool::onSwap`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L252):
  ```solidity
  } else if (request.indexIn > 4 && request.indexOut < 4) { // @audit should be >=
  ```

- In [`QuantAMMWeightedPool::_getNormalisedWeightPair`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L320):
  ```solidity
  if (tokenIndexTwo > 4) { // @audit should be >=
  ```

1. Swaps where `indexIn > 4` and `indexOut < 4` are impossible.
2. Swaps involving token index 4 cannot be performed.
3. If swaps with `indexIn > 4` and `indexOut < 4` would be possible, the swap amounts would be calculated incorrectly.

## Proof of Concept

Add the following tests to `pkg/pool-quantamm/test/foundry/QuantAMMWeightedPool8Token.t.sol` to demonstrate the issues:
```solidity
// cross swap not working correctly
function testGetNormalizedWeightOnSwapOutGivenInNBlocksAfterToken7Token3() public {
    testParam memory firstWeight = testParam(7, 0.1e18, 0.001e18); // indexIn > 4
    testParam memory secondWeight = testParam(3, 0.15e18, 0.001e18); // indexOut < 4
    // will revert on underflow
    _onSwapOutGivenInInternal(firstWeight, secondWeight, 2, 1.006410772600252500e18);
}
// index >= 4 not working correctly
function testGetNormalizedWeightOnSwapOutGivenInInitialToken0Token4() public {
    testParam memory firstWeight = testParam(0, 0.1e18, 0.15e18);
    testParam memory secondWeight = testParam(4, 0.15e18, 0.001e18);
    // fails with `panic: array out-of-bounds access`
    _onSwapOutGivenInInternal(firstWeight, secondWeight, 0, 0.499583703357018000e18);
}
// index >= 4 not working correctly
function testGetNormalizedWeightOnSwapOutGivenInInitialToken4Token0() public {
    testParam memory firstWeight = testParam(4, 0.1e18, 0.001e18);
    testParam memory secondWeight = testParam(0, 0.15e18, 0.001e18);
    // fails with `panic: array out-of-bounds access`
    _onSwapOutGivenInInternal(firstWeight, secondWeight, 0, 0.887902403682279000e18);
}
```

## Recommendation

1. **Refactor the `if` block** in `QuantAMMWeightedPool::onSwap` as follows:

   ```solidity
   if (request.indexIn < 4 && request.indexOut < 4 || request.indexIn >= 4 && request.indexOut >= 4) {
       // Same slot; _getNormalisedWeightPair handles the correct logic
       tokenWeights = _getNormalisedWeightPair(...);
   } else {
       // Cross-slot handling
       tokenWeights = _getNormalizedWeight(...);
   }
   ```

2. **Update** conditions `> 4` to `>= 4` at the following lines:

   - [Line 320](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L320)
   - [Line 383](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L383)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one error in the index boundary checks of the QuantAMMWeightedPool contract, which stores token weights in two packed slots of four entries each. The contract distinguishes tokens that reside in the first slot (indices 0‑3) from those in the second slot (indices 4‑7) by testing whether an index is less than four. In the onSwap function the second conditional branch is written as `request.indexIn > 4 && request.indexOut < 4`, and later the helper functions `_getNormalisedWeightPair` and `_getNormalizedWeight` use the test `tokenIndexTwo > 4` and `tokenIndex > 4`. These comparisons should be `>= 4` because token index 4 belongs to the second slot. Because the condition is wrong, swaps that involve a token with index 4 or any cross‑slot swap where the input token is in the second slot and the output token is in the first slot trigger a code path that assumes the token is in the first slot. This leads to an under‑flow when the code subtracts four from an index that is already less than four, and later to an array‑out‑of‑bounds access when the contract tries to read a weight at position eight of an eight‑element array. The bug was discovered during a manual audit by Cyfrin, which added targeted Foundry tests that caused the contract to revert with a panic error. The issue is hard to notice because the logic appears symmetric and the faulty branch is only exercised for a small subset of token pairs, making it easy to miss during casual testing. When an affected swap is attempted, the transaction reverts, so the user receives no output tokens and may see a UI message such as “swap failed” or “insufficient output amount”. From a business perspective the pool cannot trade certain token pairs, breaking the expected liquidity provision and accounting assumptions that any pair of tokens in the pool can be swapped. Liquidity providers lose the ability to trade those pairs, and traders are denied service, effectively a denial‑of‑service condition for those assets. The vulnerability belongs to the class of boundary‑condition bugs in storage‑packing logic, specifically off‑by‑one errors that cause under‑flow and out‑of‑bounds reads. The recommended fix is to correct the conditional checks to use `>= 4` for the second slot, unify the handling of same‑slot swaps by calling `_getNormalisedWeightPair` for both slots, and adjust the helper functions accordingly. After fixing the boundary checks, the weight calculations will correctly reference the second storage element, eliminating under‑flow and preventing array‑out‑of‑bounds panics, thereby restoring full swap functionality across all eight tokens.
