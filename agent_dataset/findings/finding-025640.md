---
id: 25640
severity: "Low/Info"
---

# ERC4626YieldBackend.withdrawMax() silently succeeds when vault is paused, leaving funds stuck

## Description



## Proof of Concept

## Vulnerability Detail

Per EIP-4626, when a vault is paused, `maxWithdraw()` should return 0 rather than revert. The `withdrawMax()` function checks if `balance > 0` before attempting withdrawal, so when a vault is paused, it simply does nothing and returns successfully.

The problem is that `SuperToken.disableYieldBackend()` calls `withdrawMax()` and then clears the yield backend reference. If the vault is paused at the time of disabling, the call succeeds but funds remain locked in the vault. Since the yield backend reference is cleared, there is no way to recover the funds afterward.

```solidity
function disableYieldBackend() external onlyAdmin {
    require(address(_yieldBackend) != address(0), "yield backend not set");
    address oldYieldBackend = address(_yieldBackend);

    _skipSelfMint = true;
    delegateCallChecked(address(_yieldBackend), abi.encodeCall(IYieldBackend.withdrawMax, ()));
    _skipSelfMint = false;

    delegateCallChecked(address(_yieldBackend), abi.encodeCall(IYieldBackend.disable, ()));
    _yieldBackend = IYieldBackend(address(0)); // Backend cleared, funds stuck!
    emit YieldBackendDisabled(oldYieldBackend);
}
```

## Impact

When `disableYieldBackend()` is called while the ERC4626 vault is paused, all funds deposited in the vault become permanently stuck. The yield backend is disabled and there is no mechanism to recover the funds.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L38-L43](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L38-L43>)

```solidity
function withdrawMax() external {
    uint256 balance = VAULT.maxWithdraw(address(this));
    if (balance > 0) {
        VAULT.withdraw(balance, address(this), address(this));
    }
}
```

## Recommendation

Add a check in `disableYieldBackend()` to verify that funds were actually withdrawn, or add a minimum expected amount parameter:

```solidity
function withdrawMax() external returns (uint256) {
    uint256 balance = VAULT.maxWithdraw(address(this));
    if (balance > 0) {
        VAULT.withdraw(balance, address(this), address(this));
    }
    return balance;
}
```

Then in `SuperToken.disableYieldBackend()`:

```solidity
function disableYieldBackend(uint256 minExpectedAmount) external onlyAdmin {
    // ... existing code ...
    uint256 withdrawn = delegateCallChecked(address(_yieldBackend), abi.encodeCall(IYieldBackend.withdrawMax, ()));
    require(withdrawn >= minExpectedAmount, "insufficient withdrawal");
    // ... rest of function ...
}
```
