---
id: 21188
severity: "High"
---

# `NoyaValueOracle.getValue` returns an incorrect price when a multi-token route is used

## Description

The [NoyaValueOracle.getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L71-L79) is used to convert the price of an `asset` to `baseToken`, using token routing when necessary.

If there is no oracle for two tokens, a route needs to be set up between them. This route can then be used to get a value using [NoyaValueOracle.getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L71-L79).

However, there’s a mistake in the [NoyaValueOracle.getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L71-L79) function that makes it give the wrong price.

## Proof of Concept

To set a price path for a token pair, the maintainer should use [NoyaValueOracle.updatePriceRoute](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L61-L64).

For instance, for the `SOL` to `UNI` conversion. 1 `SOL` is roughly equal to 21 `UNI`, but there’s no direct oracle. So, the maintainer sets a route `SOL` → `BNB` → `ETH` → `UNI`.

When [_getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L81-L93) tries to convert 100 `SOL` into `UNI`, it should first convert `SOL` → `BNB`, then `BNB` → `ETH`, and lastly `ETH` → `UNI`. But, what [_getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L81-L93) really does is to convert `SOL` → `BNB`, `SOL` → `ETH`, and `SOL` → `UNI`.

You can see this error in the [_getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L89) function, where `asset` is used each time instead of `quotingToken`.

```solidity
function _getValue(address asset, address baseToken, uint256 amount, address[] memory sources)
    internal
    view
    returns (uint256 value)
{
    uint256 initialValue = amount;
    address quotingToken = asset;
    for (uint256 i = 0; i < sources.length; i++) {
        initialValue = _getValue(asset, sources[i], initialValue);
        quotingToken = sources[i];
    }
    return _getValue(quotingToken, baseToken, initialValue);
}
```

The first problem comes up if the `SOL` → `BNB`, `SOL` → `ETH`, and `SOL` → `UNI` oracles are not set up. This will cause a revert of [_getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L95-L110).
    
```solidity
function _getValue(address quotingToken, address baseToken, uint256 amount) internal view returns (uint256) {
    INoyaValueOracle oracle = priceSource[quotingToken][baseToken];
    if (address(oracle) == address(0)) {
        oracle = priceSource[baseToken][quotingToken];
    }
    if (address(oracle) == address(0)) {
        oracle = defaultPriceSource[baseToken];
    }
    if (address(oracle) == address(0)) {
        oracle = defaultPriceSource[quotingToken];
    }
    if (address(oracle) == address(0)) {
        revert NoyaOracle_PriceOracleUnavailable(quotingToken, baseToken);
    }
    return oracle.getValue(quotingToken, baseToken, amount);
}
```

Even if we configure these oracles, the calculated value will still be incorrect.

Consider this example - the [_getValue](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/valueOracle/NoyaValueOracle.sol#L81-L93) is called with the following parameters:

* asset = SOL
* baseToken = UNI
* amount = 100
* sources = [BNB, ETH]

This will convert 100 `SOL` to `UNI`, using `BNB` and `ETH` as the route.

Iteration | initialValue | quotingToken | asset | sources[i] | initialValue’ | quotingToken’  
---|---|---|---|---|---|---  
1 | 100 | SOL | SOL | BNB | 100SOL ≈ 25BNB | BNB  
2 | 25 | BNB | SOL | ETH | 25BNB ≈ 1.25ETH | ETH  
  
The result is calculated using `quotingToken` = ETH, `baseToken` = UNI, and the `initialValue` = 1.25, which returns 526.

However, the expected result should be 2094.

## Recommendation

Replace `asset` with `quotingToken:`
    
```solidity
function _getValue(address asset, address baseToken, uint256 amount, address[] memory sources)
    internal
    view
    returns (uint256 value)
{
    uint256 initialValue = amount;
    address quotingToken = asset;
    for (uint256 i = 0; i < sources.length; i++) {
        initialValue = _getValue(quotingToken, sources[i], initialValue);
        quotingToken = sources[i];
    }
    return _getValue(quotingToken, baseToken, initialValue);
}
```

Fix in commit 66d4104e83cc1b68ab117c78c4a92eafac86341c.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the internal price conversion routine of the NoyaValueOracle contract. The routine is supposed to follow a multi‑hop route when a direct price feed between an asset and the base token does not exist. The implementation keeps a variable quotingToken that should be updated after each hop, but the loop mistakenly calls the helper _getValue with the original asset address on every iteration instead of the current quotingToken. As a result the oracle queries are performed as asset→firstHop, asset→secondHop, … rather than firstHop→secondHop, …, breaking the intended chain of conversions. This logical error causes the final price to be calculated from an incorrect intermediate token, producing a value that can be far from the true market price. In addition, if any of the unintended direct oracle pairs are missing, the function reverts with a PriceOracleUnavailable error, preventing the route from completing. The bug is triggered whenever a multi‑token route is configured through updatePriceRoute and getValue is called with a non‑empty sources array. Users of the protocol who rely on the oracle for pricing, collateral valuation, or trade execution will see prices that are too low or too high; for example a conversion of 100 SOL to UNI through SOL→BNB→ETH→UNI returns roughly 526 instead of the expected 2094. From a user perspective the UI may display a much smaller amount received after a swap or liquidation, or may simply fail with a revert message. The issue was discovered during a manual audit of the contract’s source code, where the loop variable usage was examined and found inconsistent with the intended algorithm. Because the code compiles and the function name suggests correct behavior, the bug can remain hidden until a mismatched price is observed in production. The proper fix is to replace the first argument of the internal call inside the loop with the current quotingToken, ensuring that each hop uses the output of the previous conversion as its input. This change restores the correct sequential price aggregation and eliminates the revert condition caused by missing direct oracle pairs.
