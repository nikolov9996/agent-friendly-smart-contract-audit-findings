---
id: 25639
severity: "Low/Info"
---

# AaveYieldBackend.deposit() DoS when Aave pool is paused, frozen, or at supply cap

## Description



## Proof of Concept

## Vulnerability Detail

The `deposit()` function calls `AAVE_POOL.supply()` directly without handling cases where Aave may reject the deposit. Aave pools can be paused, frozen, or have supply caps that prevent new deposits. When any of these conditions occur, all SuperToken operations that trigger deposits (such as `upgrade()`, `upgradeTo()`, and `selfMint()`) revert.

The underlying assets could simply be kept in the SuperToken contract when Aave is unavailable, but currently there is no fallback mechanism.

## Impact

Users are unable to mint or upgrade SuperTokens when the underlying Aave pool is paused, frozen, or at supply capacity. This DoSes the core functionality of the SuperToken for an indeterminate period of time until Aave governance re-enables the pool.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveYieldBackend.sol#L49-L54](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveYieldBackend.sol#L49-L54>)

```solidity
function deposit(uint256 amount) public virtual {
    // TODO: can this constraint break anything?
    require(amount > 0, "amount must be greater than 0");
    // Deposit asset and get back aTokens
    AAVE_POOL.supply(address(ASSET_TOKEN), amount, address(this), 0);
}
```

## Recommendation

Implement a try-catch mechanism to handle Aave deposit failures gracefully. When the deposit fails, keep the underlying assets in the SuperToken contract:

```solidity
function deposit(uint256 amount) public virtual {
    require(amount > 0, "amount must be greater than 0");
    try AAVE_POOL.supply(address(ASSET_TOKEN), amount, address(this), 0) {
        // Deposit succeeded
    } catch {
        // Aave deposit failed (paused, frozen, supply cap reached)
        // Keep the underlying assets in the contract
    }
}
```
