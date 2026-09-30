---
id: 22263
severity: "High"
---

# Mismatch in multiplier position causes incorrect weight calculations in `QuantAMMWeightedPool`

## Description

The primary feature of QuantAMM weighted pools is to periodically update weights based on various trading rules set during pool creation. These weights are updated by a singleton contract, `UpdateWeightRunner`, which provides new weights and multipliers. The multipliers help to adjust the weights between blocks until the next update.

To optimize gas usage compared to Balancer weighted pools, QuantAMM packs weights and multipliers into just two storage slots.

When an update occurs, `UpdateWeightRunner` sends the new weights to [`QuantAMMWeightedPool::setWeights`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L588-L615). The weights and multipliers are sent in a different format than the pool expects though, as described in the [NatSpec comment](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L696) for `QuantAMMWeightedPool::_splitWeightAndMultipliers`:

```solidity
/// @dev Update weight runner gives all weights in a single array shaped like [w1,w2,w3,w4,w5,w6,w7,w8,m1,m2,m3,m4,m5,m6,m7,m8], we need it to be [w1,w2,w3,w4,m1,m2,m3,m4,w5,w6,w7,w8,m5,m6,m7,m8]
```

The data is then split into two storage slots as follows:
- **First slot:** `[w1, w2, w3, w4, m1, m2, m3, m4]`
- **Second slot:** `[w5, w6, w7, w8, m5, m6, m7, m8]`

For a pool with just two tokens, `UpdateWeightRunner` sends the weights and multipliers as `[w1, w2, m1, m2]`, which are stored in this same order (with zeros padded at the end). However, for a pool with more tokens (e.g., 6 tokens), more complex logic is required to split the data into two slots. This is handled by [`QuantAMMWeightedPool::_splitWeightAndMultipliers`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L694-L722).

When `UpdateWeightRunner` sends the weights and multipliers for 6 tokens as `[w1, w2, w3, w4, w5, w6, m1, m2, m3, m4, m5, m6]`, the [first slot](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L700-L710) is populated like this:

```solidity
uint256 tokenLength = weights.length / 2;
splitWeights = new int256[][](2);
splitWeights[0] = new int256[](8);
for (uint i; i < 4; ) {
    splitWeights[0][i] = weights[i];
    splitWeights[0][i + 4] = weights[i + tokenLength];

    unchecked {
        i++;
    }
}
```

This results in the first slot being `[w1, w2, w3, w4, m1, m2, m3, m4]`.

The [second slot](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L711-L721) is handled with the following logic:

```solidity
splitWeights[1] = new int256[](8);
uint256 moreThan4Tokens = tokenLength - 4;
for (uint i = 0; i < moreThan4Tokens; ) {
    uint256 i4 = i + 4;
    splitWeights[1][i] = weights[i4];
    splitWeights[1][i4] = weights[i4 + tokenLength];

    unchecked {
        i++;
    }
}
```

For 6 tokens, this results in the second slot being `[w5, w6, 0, 0, m5, m6, 0, 0]`.

The issue arises when these values are read in [`QuantAMMWeightedPool::_getNormalizedWeight`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L381-L388):

```solidity
uint256 tokenIndexInPacked = totalTokens;

if (tokenIndex > 4) {
    //get the index in the second storage int
    index = tokenIndex - 4;
    targetWrappedToken = _normalizedSecondFourWeights;
    tokenIndexInPacked -= 4;
} else {
```

Here, `tokenIndexInPacked` becomes `6 - 4 = 2`, which is then used in [`QuantAMMWeightedPool::_calculateCurrentBlockWeight`](https://github.com/QuantAMMProtocol/QuantAMM-V1/blob/7213401491f6a8fd1fcc1cf4763b15b5da355f1c/pkg/pool-quantamm/contracts/QuantAMMWeightedPool.sol#L364):

```solidity
int256 blockMultiplier = tokenWeights[tokenIndex + (tokensInTokenWeights)];
```
For token index 5, or index 1 in second slot, this attempts to access the multiplier at position `1 + 2 = 3`, whereas the multiplier is actually in the fifth position. This mismatch causes incorrect multipliers or no multipliers to be used.

The incorrect reading of multipliers causes the wrong weight to be applied during token swaps. As a result, swap amounts may be incorrect, leading to unintended and potentially harmful outcomes for users.

## Proof of Concept

Add this test to `pkg/pool-quantamm/test/foundry/QuantAMMWeightedPool8Token.t.sol`:
```solidity
function testGetNormalizedWeightsInitial6Tokens() public {
    int256 weight = int256(1e18) / 6 + 1;
    PoolRoleAccounts memory roleAccounts;
    IERC20[] memory tokens = [
        address(dai),
        address(usdc),
        address(weth),
        address(wsteth),
        address(veBAL),
        address(waDAI)
    ].toMemoryArray().asIERC20();
    MockMomentumRule momentumRule = new MockMomentumRule(owner);

    int256[] memory initialWeights = new int256[](6);
    initialWeights[0] = weight;
    initialWeights[1] = weight;
    initialWeights[2] = weight - 1;
    initialWeights[3] = weight - 1;
    initialWeights[4] = weight;
    initialWeights[5] = weight;

    uint256[] memory initialWeightsUint = new uint256[](6);
    initialWeightsUint[0] = uint256(weight);
    initialWeightsUint[1] = uint256(weight);
    initialWeightsUint[2] = uint256(weight - 1);
    initialWeightsUint[3] = uint256(weight - 1);
    initialWeightsUint[4] = uint256(weight);
    initialWeightsUint[5] = uint256(weight);

    uint64[] memory lambdas = new uint64[](1);
    lambdas[0] = 0.2e18;

    int256[][] memory parameters = new int256[][](1);
    parameters[0] = new int256[](1);
    parameters[0][0] = 0.2e18;

    address[][] memory oracles = new address[][](1);
    oracles[0] = new address[](1);
    oracles[0][0] = address(chainlinkOracle);

    QuantAMMWeightedPoolFactory.NewPoolParams memory params = QuantAMMWeightedPoolFactory.NewPoolParams(
        "Pool With Donation",
        "PwD",
        vault.buildTokenConfig(tokens),
        initialWeightsUint,
        roleAccounts,
        MAX_SWAP_FEE_PERCENTAGE,
        address(0),
        true,
        false, // Do not disable unbalanced add/remove liquidity
        ZERO_BYTES32,
        initialWeights,
        IQuantAMMWeightedPool.PoolSettings(
            new IERC20[](6),
            IUpdateRule(momentumRule),
            oracles,
            60,
            lambdas,
            0.01e18,
            0.01e18,
            0.01e18,
            parameters,
            address(0)
        ),
        initialWeights,
        initialWeights,
        3600,
        0,
        new string[][](0)
    );

    address quantAMMWeightedPool = quantAMMWeightedPoolFactory.create(params);

    uint256[] memory weights = QuantAMMWeightedPool(quantAMMWeightedPool).getNormalizedWeights();

    int256[] memory newWeights = new int256[](12);
    newWeights[0] = weight;
    newWeights[1] = weight;
    newWeights[2] = weight - 1;
    newWeights[3] = weight - 1;
    newWeights[4] = weight;
    newWeights[5] = weight;
    newWeights[6] = 0.001e18;
    newWeights[7] = 0.001e18;
    newWeights[8] = 0.001e18;
    newWeights[9] = 0.001e18;
    newWeights[10] = 0.001e18;
    newWeights[11] = 0.001e18;

    vm.prank(address(updateWeightRunner));
    QuantAMMWeightedPool(quantAMMWeightedPool).setWeights(
        newWeights,
        quantAMMWeightedPool,
        uint40(block.timestamp + 5)
    );

    uint256[] memory balances = new uint256[](6);
    balances[0] = 1000e18;
    balances[1] = 1000e18;
    balances[2] = 1000e18;
    balances[3] = 1000e18;
    balances[4] = 1000e18;
    balances[5] = 1000e18;

    PoolSwapParams memory swapParams = PoolSwapParams({
        kind: SwapKind.EXACT_IN,
        amountGivenScaled18: 1e18,
        balancesScaled18: balances,
        indexIn: 0,
        indexOut: 1,
        router: address(router),
        userData: abi.encode(0)
    });

    vm.warp(block.timestamp + 5);

    vm.prank(address(vault));
    uint256 swap1Balance = QuantAMMWeightedPool(quantAMMWeightedPool).onSwap(swapParams);

    swapParams.indexOut = 5;

    vm.prank(address(vault));
    uint256 swap5Balance = QuantAMMWeightedPool(quantAMMWeightedPool).onSwap(swapParams);

    assertEq(swap1Balance, swap5Balance);
}
```

## Recommendation

Consider storing the second slot the same way as the first one:
```diff
- splitWeights[1][i4] = weights[i4 + tokenLength];
+ splitWeights[1][i + moreThan4Tokens] = weights[i4 + tokenLength];
```
This will also require changes to `getNormalizedWeights` as it assumes a distance of 4 in the second weight slot.

**[Project]:**
Fixed in commit [`31636cf`](https://github.com/QuantAMMProtocol/QuantAMM-V1/commit/31636cf736e9f6eda09f569bceb4e8d9bd3137bb) and [`8a6b3b2`](https://github.com/QuantAMMProtocol/QuantAMM-V1/commit/8a6b3b2d8ecd8cb52ecd652a0c3e02ab4964e8df)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a misalignment between the positions of weight multipliers and their storage slots in QuantAMM weighted pools that use more than four tokens. QuantAMM stores eight values per slot, packing four token weights followed by four multipliers into two 256‑bit slots to save gas. When the singleton UpdateWeightRunner supplies a flat array of weights and multipliers, the contract splits this array into the two slots. The first slot is built correctly, but the logic that fills the second slot writes the multipliers at indices that are offset by the number of tokens beyond the fourth, rather than at the fixed positions expected by the read routine. Consequently, when the pool later reads a multiplier for a token that resides in the second slot, it accesses an empty or wrong element, applying an incorrect multiplier to the token’s weight. This error only manifests for pools with more than four tokens because the second‑slot layout is never exercised in smaller pools. The bug was discovered during a formal audit when a test that updated six‑token weights produced identical swap outputs for unrelated token pairs, indicating that the weight calculation was not reflecting the supplied multipliers. From a user’s perspective the pool appears to accept a weight update, but subsequent swaps return amounts that are too high or too low, or in extreme cases the pool may return zero output, violating the expectation that a swap of a given amount yields a predictable amount of the target token. The impact is that traders receive incorrect pricing, potentially losing value, and the protocol’s accounting invariants are broken because the normalized weights no longer sum to the intended total. The issue is hard to notice because the contract does not emit an explicit error; the wrong multiplier is silently used, and the resulting price deviation may be attributed to market volatility. The root cause is an indexing mismatch in the split‑and‑store routine for the second storage slot, a classic storage‑layout or off‑by‑one bug rather than an arithmetic overflow. The recommended fix is to store the second slot using the same fixed offset as the first slot, aligning multipliers with the positions assumed by the weight‑normalisation functions, and to adjust the getter logic accordingly. After correcting the layout, the pool will correctly apply the intended multipliers, restoring accurate weight updates and reliable swap outcomes.
