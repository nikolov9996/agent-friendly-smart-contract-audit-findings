---
id: 25638
severity: "Medium"
---

# Aave rounding behavior allows malicious users to drain accumulated yield via small withdrawals

## Description



## Proof of Concept

## Vulnerability Detail

When depositing to Aave, the scaled balance received is rounded down (`scaledBalance = amount / index`). When withdrawing, Aave rounds up the scaled balance burned (`scaledBalanceBurned = ceil(amount / index)`). The SuperToken mints/burns tokens at a 1:1 ratio with the requested amount, ignoring these rounding discrepancies.

Consider this scenario with an Aave index of 2:

- Two users each have 50 SuperTokens, backed by 100 aTokens total (50 scaled balance)
- A malicious user withdraws their 50 SuperTokens in a loop, 1 wei at a time
- Each 1 wei withdrawal burns `ceil(1/2) = 1` scaled balance
- After 50 iterations, the user has withdrawn 50 wei but burned all 50 scaled balance
- The second user's 50 SuperTokens are now backed by 0 aTokens

The attack is particularly impactful for tokens like WBTC where 1 wei equals ~$0.001, making the gas cost worthwhile for the attacker.

**Numerical Example:**

1. Aave index = 1.1
2. User deposits 50 tokens → receives `50 / 1.1 = 45` scaled balance (rounded down)
3. Aave holds `45 * 1.1 = 49.5 ≈ 49` aTokens (not 50)
4. Index grows to 1.15
5. User withdraws 48 aTokens → burns `ceil(48 / 1.15) = 42` scaled balance
6. Remaining: `45 - 42 = 3` scaled balance = `3 * 1.15 = 3.45` aTokens
7. Yield lost: `45 * 1.15 - 48 - 3.45 = 0.3` aTokens due to rounding

## Impact

A malicious user can systematically drain all accumulated Aave yield by performing repeated small withdrawals. This results in loss of yield for all SuperToken holders and potential insolvency where the total SuperToken supply exceeds the backing aTokens.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/SuperToken.sol#L778-L779](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/SuperToken.sol#L778-L779>)

```solidity
        _mint(msg.sender, account, amount, userData.length != 0 /* invokeHook */,
            userData.length != 0 /* requireReceptionAck */, userData, new bytes(0));
```

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveYieldBackend.sol#L56-L59](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/AaveYieldBackend.sol#L56-L59>)

```solidity
function withdraw(uint256 amount) public virtual {
    // withdraw amount asset by redeeming the corresponding aTokens amount
    AAVE_POOL.withdraw(address(ASSET_TOKEN), amount, address(this));
}
```

## Recommendation

Modify the withdrawal to request a slightly lower amount from Aave that accounts for rounding, while still burning the full SuperToken amount requested by the user:

```solidity
function withdraw(uint256 requestedAmount) public virtual returns (uint256) {
    uint256 index = AAVE_POOL.getReserveNormalizedIncome(address(ASSET_TOKEN));
    uint256 scaledAmount = (requestedAmount * 1e27) / index;
    uint256 safeWithdrawAmount = (scaledAmount * index) / 1e27;
    AAVE_POOL.withdraw(address(ASSET_TOKEN), safeWithdrawAmount, address(this));
}
```

This ensures the scaled balance burned matches the expected value, and the user takes the rounding loss.
