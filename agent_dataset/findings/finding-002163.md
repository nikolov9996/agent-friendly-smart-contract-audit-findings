---
id: 2163
severity: "High"
---

# Reward claiming fails for Berachain RewardVaults due to incorrect interface

## Description

** D2 plans to deploy on the newly launched Berachain, which operates on a novel [Proof-of-Liquidity](https://docs.berachain.com/learn/what-is-proof-of-liquidity) model. On Berachain, liquidity providers can stake their LP tokens in [Reward Vaults](https://docs.berachain.com/developers/contracts/reward-vault) to earn `$BGT`, the Berachain Governance Token.

To facilitate staking and withdrawals, the D2 [`Bera_Module`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/modules/Bera.sol) includes the functions [`Bera_Module::bera_vault_stake`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/modules/Bera.sol#L66-L68) and [`Bera_Module::bera_vault_withdraw`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/modules/Bera.sol#L70-L72). To claim `$BGT` rewards, the [`Bera_Module::bera_vault_get_reward`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/modules/Bera.sol#L74-L76) function is used:

```solidity
function bera_vault_get_reward(address token) external onlyRole(EXECUTOR_ROLE) nonReentrant {
    IVault(vaultFactory.getVault(token)).getReward(address(this));
}
```

However, the interface used for [`IVault::getReward`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/modules/Bera.sol#L221) is incorrect:

```solidity
function getReward(address account) external;
```

In Berachain’s [`RewardVault::getReward`](https://github.com/berachain/contracts/blob/main/src/pol/rewards/RewardVault.sol#L318-L321) and as deployed on-chain, the correct function signature is:

```solidity
function getReward(
    address account,
    address recipient
)
```

Due to this discrepancy, any call to `Bera_Module::bera_vault_get_reward` will revert, preventing `$BGT` rewards from being claimed.

** The `$BGT` rewards, which are a core incentive of Berachain's Proof-of-Liquidity model, cannot be claimed. This reduces the protocol's ability to effectively participate in Berachain’s reward system. Additionally, since these rewards contribute to the protocol's overall earnings.

## Proof of Concept

** The following test highlights the issue:
```solidity
function test_bera_vault_get_reward() public {
    deal(USDCe_HONEY_STABLE_ADDRESS, address(strategy), 1e18);

    vm.startPrank(EXECUTOR);
    trader.approve(USDCe_HONEY_STABLE_ADDRESS, USDCe_HONEY_STABLE_VAULT, 1e18);
    bera.bera_vault_stake(USDCe_HONEY_STABLE_ADDRESS, 1e18);

    assertEq(RewardVault(USDCe_HONEY_STABLE_VAULT).balanceOf(address(strategy)), 1e18);

    vm.warp(block.timestamp + 1 days);

    // there are rewards to be claimed
    assertGt(RewardVault(USDCe_HONEY_STABLE_VAULT).earned(address(strategy)), 0);

    // rewards cannot be claimed due to the interface definition being wrong
    vm.expectRevert();
    bera.bera_vault_get_reward(USDCe_HONEY_STABLE_ADDRESS);

    vm.stopPrank();
}
```

## Recommendation

** Consider adding the extra parameter to the interface and call it with `address(this)`:
```diff
    IVault(vaultFactory.getVault(token)).getReward(address(this));
    IVault(vaultFactory.getVault(token)).getReward(address(this), address(this));
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an interface mismatch between the D2 module that attempts to claim rewards from a Berachain RewardVault and the actual RewardVault contract implementation. The module calls IVault.getReward(address) while the deployed RewardVault expects a function signature getReward(address account, address recipient). Because the second parameter is missing, the low‑level call is encoded with the wrong calldata, causing the external call to revert at runtime. This mismatch occurs whenever the function bera_vault_get_reward is invoked, which is restricted to the EXECUTOR_ROLE but can be called by any authorized executor. As a result, any attempt to claim $BGT rewards fails, leaving the rewards unclaimed and the caller receiving no tokens. From a user perspective the claim transaction reverts, the UI may show an error or simply no change in balance, and users see that their expected reward amount remains zero despite having earned rewards. The issue was discovered during a security audit when a test that expected a successful claim instead triggered an expectRevert, confirming that the call could not succeed. The bug is hard to notice because the Solidity code compiles without errors—the interface definition matches the compiler’s expectations—but the runtime ABI does not match the on‑chain contract, leading to silent failures only observable at execution time. This class of bug falls under incorrect interface or ABI mismatch, which violates the accounting assumption that a successful claim transfers earned tokens to the caller. To remediate, the interface definition must be updated to include the recipient argument and the call should pass address(this) for both parameters, aligning the calldata with the actual contract signature. After fixing, reward claims will succeed, restoring the protocol’s incentive mechanism and allowing liquidity providers to receive their earned $BGT tokens.
