---
id: 25637
severity: "Medium"
---

# AaveETHYieldBackend uses wrong WETH address for Polygon (returns WETH instead of WPOL)

## Description



## Proof of Concept

## Vulnerability Detail

In `getWETHAddress()`, for chain ID 137 (Polygon), the contract returns the WETH address (`0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619`) which is a bridged ETH token, instead of the native token wrapper WPOL at `0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270`.

The contract is designed to wrap native ETH/tokens to their wrapped ERC20 equivalent and deposit them to Aave. On Polygon, native tokens (POL/MATIC) should be wrapped to WPOL, not WETH. WETH on Polygon is simply a bridged representation of Ethereum's ETH and is not the native token wrapper.

## Impact

The `AaveETHYieldBackend` is unusable on Polygon. When users try to deposit native POL, the contract attempts to interact with the WETH contract which does not have a `deposit()` function that accepts native POL, causing all deposits to fail.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveETHYieldBackend.sol#L46-L48](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveETHYieldBackend.sol#L46-L48>)

```solidity
if (block.chainid == 137) { // Polygon
    return 0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619; //@audit ISSUE WETH not WPOL, WPOL is 0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270
}
```

## Recommendation

Return the correct WPOL address for Polygon:

```solidity
if (block.chainid == 137) { // Polygon
    // Note this token has the symbol WPOL, wrapping the native token POL
    return 0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270;
}
```
