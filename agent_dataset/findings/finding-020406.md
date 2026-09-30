---
id: 20406
severity: "High"
---

# Fewer than expected LP tokens if the pool is

## Description

The vault restoration function intends to perform a proportional deposit. If the pool is imbalanced due to unexpected circumstances, performing a proportional deposit is not optimal. This results in fewer pool tokens in return due to sub-optimal trade, eventually leading to a loss for the vault shareholder. intends to deposit the withdrawn tokens back into the pool proportionally.
File: SingleSidedLPVaultBase.sol
```solidity
/// @notice Restores withdrawn tokens from emergencyExit back into the vault proportionally.
/// Unlocks the vault after restoration so that normal functionality is restored.
/// @param minPoolClaim slippage limit to prevent front running
function restoreVault(
    uint256 minPoolClaim, bytes calldata /* data */
) external override whenLocked onlyNotionalOwner {
    StrategyVaultState memory state = VaultStorage.getStrategyVaultState();

    (IERC20[] memory tokens, /* */) = TOKENS();
    uint256[] memory amounts = new uint256[](tokens.length);

    // All balances held by the vault are assumed to be used to re-enter
    // the pool. Since the vault has been locked no other users should have
    // been able to enter the pool.
    for (uint256 i; i < tokens.length; i++) {
        if (address(tokens[i]) == address(POOL_TOKEN())) continue;
        amounts[i] = TokenUtils.tokenBalance(address(tokens[i]));
    }

    // No trades are specified so this joins proportionally using the
    // amounts specified.
    uint256 poolTokens = _joinPoolAndStake(amounts, minPoolClaim);
```
The main reason to join with all the pool's tokens in exact proportions is to minimize the price impact or slippage of the join. If the deposited tokens are imbalanced, they are often swapped internally within the pool, incurring slippage or fees. However, the concept of proportional join to minimize slippage does not always hold with the current implementation of the restoreVault function. There is no guarantee that a pool will always be balanced. Historically, there have been multiple instances where the largest curve pool (stETH/ETH) has become imbalanced (Reference #1 and #2). If the pool is imbalanced due to unexpected circumstances, performing a proportional deposit is not optimal, leading to the deposit resulting in fewer LP tokens than possible due to the deposit penalty or slippage due to internal swap. The side-effect is that the vault restoration will result in fewer pool tokens in return due to sub-optimal trade, eventually leading to a loss of assets for the vault shareholder.

## Proof of Concept

1) At T0, assume that a pool is perfectly balanced (50%-50%) with 1000 WETH and 1000 stETH.
2) At T1, an emergency exit is performed, the LP tokens are redeemed for the underlying pool tokens proportionally, and 100 WETH and 100 stETH are redeemed.
3) At T2, certain events happen or due to ongoing issues with the pool (e.g., attacks, bugs, mass withdrawal), the pool becomes imbalanced (30%-70%) with 540 WETH and 1260 stETH.
4) At T3, the vault re-enters the withdrawn tokens to the pool proportionally with 100 WETH and 100 stETH. Since the pool is already imbalanced, attempting to enter the pool proportionally (50% WETH and 50% stETH) will incur additional slippage and penalties, resulting in fewer LP tokens returned.
This issue affects both Curve and Balancer pools since joining an imbalanced pool will always incur a loss.
Explantation of imbalance pool
A Curve pool is considered imbalanced when there is an imbalance between the assets within it. For instance, the Curve stETH/ETH pool is considered imbalanced if it has the following reserves:
• ETH: 340,472.34 (31.70%)
• stETH: 733,655.65 (68.30%)
If a Curve Pool is imbalanced, attempting to perform a proportional join will not give an optimal return (e.g. result in fewer Pool LP tokens received). In Curve Pool, there are penalties/bonuses when depositing to a pool. The pools are always trying to balance themselves. If a deposit helps the pool to reach that desired balance, a deposit bonus will be given (receive extra tokens). On the other hand, if a deposit deviates from the pool from the desired balance, a deposit penalty will be applied (receive fewer tokens).
The following is the source code of add_liquidity function taken from https://github.com/curvefi/curve-contract/blob/master/contracts/pools/steth/StableSwapSTETH.vy. As shown below, the function attempts to calculate the difference between the ideal_balance and new_balances, and uses the difference as a factor of the fee computation, which is tied to the bonus and penalty.
```solidity
def add_liquidity(amounts: uint256[N_COINS], min_mint_amount: uint256) -> uint256:
    ..SNIP..
    if token_supply > 0:
        # Only account for fees if we are not the first to deposit
        fee: uint256 = self.fee * N_COINS / (4 * (N_COINS - 1))
        admin_fee: uint256 = self.admin_fee
        for i in range(N_COINS):
            ideal_balance: uint256 = D1 * old_balances[i] / D0
            difference: uint256 = 0
            if ideal_balance > new_balances[i]:
                difference = ideal_balance - new_balances[i]
            else:
                difference = new_balances[i] - ideal_balance
            fees[i] = fee * difference / FEE_DENOMINATOR
            if admin_fee != 0:
                self.admin_balances[i] += fees[i] * admin_fee / FEE_DENOMINATOR
            new_balances[i] -= fees[i]
        D2 = self.get_D(new_balances, amp)
        mint_amount = token_supply * (D2 - D0) / D0
    else:
        mint_amount = D1
        # Take the dust if there was any
    ..SNIP..
```
Following is the mathematical explanation of the penalties/bonuses extracted from Curve's Discord channel:
• There is a “natural” amount of D increase that corresponds to a given total deposit amount; when the pool is perfectly balanced, this D increase is optimally achieved by a balanced deposit. Any other deposit proportions for the same total amount will give you less D.
• However, when the pool is imbalanced, a balanced deposit is no longer optimal for the D increase.

## Recommendation

Consider providing the callers the option to deposit the reward tokens in a "non-proportional" manner if a pool becomes imbalanced. For instance, the function could allow the caller to swap the withdrawn tokens in external DEXs within the restoreVault function to achieve the most optimal proportion to minimize the penalty and slippage when re-entering the pool. This is similar to the approach in the vault's reinvest function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the vault restoration routine that blindly performs a proportional join of withdrawn assets back into a liquidity pool. The function assumes that the pool’s token reserves are balanced, so it deposits the recovered tokens in the same ratio as the pool’s original composition. In reality, external events such as attacks, large withdrawals, or oracle failures can shift the pool into an imbalanced state where one asset dominates the reserve. When the restoreVault function is called while the pool is imbalanced, the proportional deposit no longer matches the pool’s current optimal ratio. The pool’s internal pricing mechanism then applies a deposit penalty or extra slippage because the added liquidity pushes the pool further away from its target balance. As a result, the vault receives fewer LP tokens than it would have if it had deposited the assets in a non‑proportional or optimally re‑balanced manner. This loss directly reduces the value of the vault’s share for its investors, causing a shortfall in expected returns. The issue manifests after an emergency exit when the vault holds the underlying tokens and attempts to re‑enter the pool; if the pool’s composition has changed between the exit and the restore call, the proportional join becomes sub‑optimal. The affected parties are the vault shareholders, the protocol that relies on accurate accounting of LP shares, and any users who expect their withdrawn assets to be fully restored. The flaw was identified during a security audit that examined the restoreVault implementation and compared it against known cases of pool imbalance in Curve’s stETH/ETH pool and similar Balancer pools. It is difficult to notice because the function executes without emitting explicit warnings, and the loss appears only as a modest reduction in LP token balance, which may be attributed to normal market variance. Conceptually, the bug belongs to the class of economic‑logic errors where a contract assumes external state invariants (balanced pool) that are not guaranteed, leading to sub‑optimal asset reallocation. From a user perspective, after a restoration the vault’s LP token balance is lower than expected, the share price appears to have dropped, and users may see “fewer pool tokens” or “missing rewards” despite having supplied the same amount of underlying assets. The correct mitigation is to avoid the hard‑coded proportional deposit; instead the contract should either detect pool imbalance and compute an optimal deposit ratio, or allow the caller to perform external swaps to achieve a composition that minimizes penalties, similar to the reinvest logic used elsewhere in the vault. By adapting the deposit strategy to the current pool state, the vault can preserve the full value of the withdrawn assets and protect shareholders from inadvertent loss.
