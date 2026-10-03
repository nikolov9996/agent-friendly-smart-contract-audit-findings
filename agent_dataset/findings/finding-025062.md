---
id: 25062
severity: "Low/Info"
---

# IDORoundConfig.idoPrice could have a comment somewhere specifying the units for better readability

## Description

`IDORoundConfig.idoPrice` is used when converting from `IdoToken` to `buyToken` or `fyToken`, but there is no indication of the code of its units. When participating in rounds, the resulting `IdoToken` are calculated from the transferred `buyToken` or `fyToken` amounts by doing:

```solidity
uint256 tokenAllocation = (amount * 10**idoConfig.idoTokenDecimals) / idoConfig.idoPrice;
```

Where `amount` is the quantity of `buyToken` or `fyToken`. This means that for the units to be correct, `idoConfig.idoPrice` must represent the `buyToken` or `fyToken` price per `IdoToken`, with units of `buyToken` and `fyToken`. Additionally, `buyToken` and `fyToken` must have the same number of decimals. IdoToken has 18 decimals, assuming `buyToken` has 6 decimals and each `IdoToken` is worth 2 `buyToken`, so the `idoPrice` is `2e6`, if we specify an amount of `buyToken` of `100e6`, we would get:

```solidity
uint256 tokenAllocation = (100e6 * 1e18) / 2e6; == 50e18
```

This is correct as 1 `idoToken` is worth 2 `buyToken` and the final decimals are `1e18`, the decimals of `IdoToken`.

## Proof of Concept

No PoC provided.

## Recommendation

Place a comment in the code indicating that the `IdoPrice` is the `buy/fyToken` price per `IdoToken` with `buy/fyToken` decimals.
