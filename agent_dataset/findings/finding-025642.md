---
id: 25642
severity: "Low/Info"
---

# ERC4626YieldBackend does not support vaults with deposit/withdrawal fees or slashing

## Description



## Proof of Concept

## Vulnerability Detail

The `ERC4626YieldBackend` mints/burns SuperTokens at a 1:1 ratio with the underlying asset amount, but many ERC4626 vaults charge deposit and/or withdrawal fees. When a user deposits into a vault with fees, fewer shares are received than expected. When withdrawing, more shares are burned than expected. Since the SuperToken mints the exact requested amount regardless of fees, other users absorb the loss.

Additionally, vaults with slashing mechanisms (e.g., staking vaults where validators can be slashed) are problematic because losses are never socialized among SuperToken users. The vault's balance decreases, but the SuperToken's total supply remains unchanged, leading to insolvency where the last users to withdraw cannot redeem their tokens.

## Impact

1. Users who deposit/withdraw cause losses to other SuperToken holders, as fees are effectively paid from the shared pool.
2. A slashing event causes the SuperToken to become insolvent - the total supply of SuperTokens exceeds the actual underlying assets available, and some users are unable to redeem their tokens.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L10-L19](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L10-L19>)

```solidity
/// @title A SuperToken yield backend for ERC4626 compliant vaults.
contract ERC4626YieldBackend is IYieldBackend {
    IERC20 public immutable ASSET_TOKEN;
    IERC4626 public immutable VAULT;
    address public immutable SURPLUS_RECEIVER;

    constructor(IERC4626 vault, address surplusReceiver) {
        VAULT = vault;
        ASSET_TOKEN = IERC20(vault.asset());
        SURPLUS_RECEIVER = surplusReceiver;
    }
```

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L29-L36](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L29-L36>)

```solidity
function deposit(uint256 amount) external {
    require(amount > 0, "amount must be greater than 0");
    VAULT.deposit(amount, address(this));
}

function withdraw(uint256 amount) external {
    VAULT.withdraw(amount, address(this), address(this));
}
```

## Recommendation

1. Document that `ERC4626YieldBackend` only supports well-behaved vaults without fees or slashing (e.g., sDAI).
2. Consider adding validation in the constructor or `enable()` to check if the vault charges fees by comparing `previewDeposit()`/`previewWithdraw()` with actual amounts.
3. For broader vault support, track actual shares received/burned and adjust SuperToken minting/burning accordingly, or implement a mechanism to socialize losses among SuperToken holders.
