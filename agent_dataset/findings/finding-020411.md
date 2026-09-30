---
id: 20411
severity: "High"
---

# Single-sided instead of proportional exit is performed during emergency exit

## Description

Single-sided instead of proportional exit is performed during emergency exit, which could lead to a loss of assets during emergency exit and vault restoration. The function is designed to allow proportional exit of underlying tokens during an emergency exit. However, it was found that the _unstakeAndExitPool function is executed with the isSingleSided parameter set to true.
```solidity
/// @notice Allows the emergency exit role to trigger an emergency exit on the vault.
/// In this situation, the `claimToExit` is withdrawn proportionally to the underlying
/// tokens and held on the vault. The vault is locked so that no entries, exits or
/// valuations of vaultShares can be performed.
/// @param claimToExit if this is set to zero, the entire pool claim is withdrawn
function emergencyExit(
    uint256 claimToExit, bytes calldata /* data */
) external override onlyRole(EMERGENCY_EXIT_ROLE) {
    StrategyVaultState memory state = VaultStorage.getStrategyVaultState();
    if (claimToExit == 0) claimToExit = state.totalPoolClaim;

    // By setting min amounts to zero, we will accept whatever tokens come from the pool
    // in a proportional exit. Front running will not have an effect since no trading will
    // occur during a proportional exit.
    _unstakeAndExitPool(claimToExit, new uint256[](NUM_TOKENS()), true);
```
If the isSingleSided is set to True, the EXACT_BPT_IN_FOR_ONE_TOKEN_OUT will be used, which is incorrect. Per the Balancer's documentation, EXACT_BPT_IN_FOR_ONE_TOKEN_OUT is a single asset exit where the user sends a precise quantity of BPT, and receives an estimated but unknown (computed at run time) quantity of a single token. To perform a proportional exit, the EXACT_BPT_IN_FOR_TOKENS_OUT should be used instead.
```solidity
function _unstakeAndExitPool(
    uint256 poolClaim, uint256[] memory minAmounts, bool isSingleSided
) internal override returns (uint256[] memory exitBalances) {
    bool success = AURA_REWARD_POOL.withdrawAndUnwrap(poolClaim, false); // claimRewards = false
    require(success);

    bytes memory customData;
    if (isSingleSided) {
..SNIP..
        uint256 primaryIndex = PRIMARY_INDEX();
        customData = abi.encode(
            IBalancerVault.ComposableExitKind.EXACT_BPT_IN_FOR_ONE_TOKEN_OUT,
            poolClaim,
            primaryIndex < BPT_INDEX ? primaryIndex : primaryIndex - 1
        );
```
The same issue affects the Curve's implementation of the _unstakeAndExitPool function.
```solidity
function _unstakeAndExitPool(
    uint256 poolClaim, uint256[] memory _minAmounts, bool isSingleSided
) internal override returns (uint256[] memory exitBalances) {
..SNIP..
    ICurve2TokenPool pool = ICurve2TokenPool(CURVE_POOL);
    exitBalances = new uint256[](2);
    if (isSingleSided) {
        // Redeem single-sided
        exitBalances[_PRIMARY_INDEX] = pool.remove_liquidity_one_coin(
            poolClaim, int8(_PRIMARY_INDEX), _minAmounts[_PRIMARY_INDEX]
        );
```
The following are some of the impacts of this issue, which lead to loss of assets:
1. Redeeming LP tokens one-sided incurs unnecessary slippage as tokens have to be swapped internally to one specific token within the pool, resulting in fewer assets received.
2. Since proportional exit is not performed, the emergency exit will be subjected to front-run attack and slippage.
```solidity
// By setting min amounts to zero, we will accept whatever tokens come from the pool
// in a proportional exit. Front running will not have an effect since no trading will
// occur during a proportional exit.
_unstakeAndExitPool(claimToExit, new uint256[](NUM_TOKENS()), true);
```
3. After the emergency exit, the vault only held one of the pool tokens. To re-enter the pool, the vault has to either swap the token to other pool tokens on external DEXs to maintain the proportion or perform a single-sided join. Both of these methods will incur unnecessary slippage, resulting in fewer LP tokens received at the end.

## Proof of Concept

no poc

## Recommendation

Set the isSingleSided parameter to false when calling the _unstakeAndExitPool function to ensure that the proportional exit is performed.
```solidity
function emergencyExit(
    uint256 claimToExit, bytes calldata /* data */
) external override onlyRole(EMERGENCY_EXIT_ROLE) {
    StrategyVaultState memory state = VaultStorage.getStrategyVaultState();
    if (claimToExit == 0) claimToExit = state.totalPoolClaim;
..SNIP..
-   _unstakeAndExitPool(claimToExit, new uint256[](NUM_TOKENS()), true);
+   _unstakeAndExitPool(claimToExit, new uint256[](NUM_TOKENS()), false);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an emergency exit routine that is intended to withdraw a user's claim from a liquidity pool in a proportional manner, preserving the relative composition of the underlying assets. In the implementation, the internal function that performs the pool withdrawal is invoked with the boolean flag isSingleSided set to true. This flag directs the Balancer and Curve adapters to execute a single‑asset exit (EXACT_BPT_IN_FOR_ONE_TOKEN_OUT on Balancer and remove_liquidity_one_coin on Curve) instead of the proportional exit (EXACT_BPT_IN_FOR_TOKENS_OUT). The root cause is a logical error where the code comment and business expectation describe a proportional exit, but the actual call forces a single‑sided redemption. When the emergencyExit function is called, the contract withdraws the specified amount of pool claim, then immediately calls _unstakeAndExitPool with isSingleSided true, causing the pool’s LP tokens to be converted into only one of the pool’s constituent tokens. This conversion incurs internal swap slippage and opens the transaction to front‑running because the price of the single token can be manipulated before the exit is finalized. As a result, the vault ends up holding only one token after the emergency exit, reducing the total value of assets retained, and requiring additional swaps or single‑sided joins to restore the original token mix, each incurring further slippage. Users therefore experience symptoms such as a missing token balance, lower overall vault value, or a zero balance for one of the expected assets, contrary to the expectation that the emergency exit returns the full claim proportionally. The issue is discovered during a security audit by Sherlock, who noted the mismatch between the documented proportional exit and the actual single‑sided call. It can be hard to notice because the function sets minimum amounts to zero, silently accepting any amount of tokens returned, and the comment suggests front‑running protection that does not apply to a single‑asset exit. The vulnerability belongs to the class of “incorrect exit mode selection” bugs, where a flag or parameter selects an unintended withdrawal path, breaking accounting assumptions and leading to asset loss. To remediate, the isSingleSided flag should be set to false when calling _unstakeAndExitPool, ensuring that the proportional exit kind (EXACT_BPT_IN_FOR_TOKENS_OUT) is used, thereby preserving token ratios and preventing unnecessary slippage and front‑run exposure.
