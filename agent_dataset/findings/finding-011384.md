---
id: 11384
severity: "High"
---

# Incorrect vault debt validation logic in rebalanceVaultsAssets causes reverts

## Description

The validation logic in CreditDelegationBranch.sol:rebalanceVaultsAssets() incorrectly reverts when the in-credit vault has a negative unsettledRealizedDebt and the in-debt vault has a positive unsettledRealizedDebt. This is not how function description says, the in-credit vault should have a deficit (< 0), and the in-debt vault should have a surplus (> 0).

CreditDelegationBranch.sol:rebalanceVaultsAssets() function descriptions states that in-credit vault should have negative unsettledRealizedDebt while in-debt vault should have positive unsettledRealizedDebt:

```solidity
/// @notice Rebalances credit and debt between two vaults.
/// @dev There are multiple factors that may result on vaults backing the same engine having a completely
/// different credit or debt state, such as:
///  - connecting vaults with markets in different times
///  - connecting vaults with different sets of markets
///  - users swapping the engine's usd token for assets of different vaults
/// This way, from time to time, the system keepers must rebalance vaults with a significant state difference in
/// order to facilitate settlement of their credit and debt. A rebalancing doesn't need to always fully settle the
/// amount of USDC that a vault in credit requires to settle its due amount, so the system is optimized to ensure
/// a financial stability of the protocol.
/// @dev Example:
///  in credit vault markets realized debt = -100 -> -90
///  in credit vault deposited usdc = 200 -> 210
///  in credit vault unsettled realized debt = -300 | as -100 + -200 -> after settlement -> -300 | as -90 + -210
///  = -300
///
///  thus, we need to rebalance as the in credit vault doesn't own enough usdc to settle its due credit
///
///  in debt vault markets realized debt = 50 -> 40
///  in debt vault deposited usdc = 10 -> 0
///  in debt vault unsettled realized debt = 40 | as 50 + -10  -> after settlement -> 40 | as 40 + 0 = 40
/// @dev The first vault id passed is assumed to be the in credit vault, and the second vault id is assumed to be
/// the in debt vault.
/// @dev The final unsettled realized debt of both vaults MUST remain the same after the rebalance.
/// @dev The actual increase or decrease in the vaults' unsettled realized debt happen at settleVaultsDebt.
/// @param vaultsIds The vaults' identifiers to rebalance.
function rebalanceVaultsAssets(uint128[2] calldata vaultsIds) external onlyRegisteredSystemKeepers {
    // load the storage pointers of the vaults in net credit and net debt
    Vault.Data storage inCreditVault = Vault.loadExisting(vaultsIds[0]);
    Vault.Data storage inDebtVault = Vault.loadExisting(vaultsIds[1]);

    // both vaults must belong to the same engine in order to have their debt
    // state rebalanced, as each usd token's debt is isolated
    if (inCreditVault.engine != inDebtVault.engine) {
        revert Errors.VaultsConnectedToDifferentEngines();
    }

    // create an in-memory dynamic array in order to call Vault::recalculateVaultsCreditCapacity
    uint256[] memory vaultsIdsForRecalculation = new uint256[](2);
    vaultsIdsForRecalculation[0] = vaultsIds[0];
    vaultsIdsForRecalculation[1] = vaultsIds[1];

    // recalculate the credit capacity of both vaults
    Vault.recalculateVaultsCreditCapacity(vaultsIdsForRecalculation);

    // cache the in debt vault & in credit vault unsettled debt
    SD59x18 inDebtVaultUnsettledRealizedDebtUsdX18 = inDebtVault.getUnsettledRealizedDebt();
    SD59x18 inCreditVaultUnsettledRealizedDebtUsdX18 = inCreditVault.getUnsettledRealizedDebt();

    // revert if 1) the vault that is supposed to be in credit is not OR
    //           2) the vault that is supposed to be in debt is not
    if (
        inCreditVaultUnsettledRealizedDebtUsdX18.lte(SD59x18_ZERO)
            || inDebtVaultUnsettledRealizedDebtUsdX18.gte(SD59x18_ZERO)
    ) {
        revert Errors.InvalidVaultDebtSettlementRequest();
    }
    ...
}
```

But this code block is doing the opposite:

```solidity
// @AUDIT this is not how requirement should be
// contract should revert if inCreditVaultUnsettledRealizedDebtUsdX18 >= 0
// or inDebtVaultUnsettledRealizedDebtUsdX18 <= 0
if (
    inCreditVaultUnsettledRealizedDebtUsdX18.lte(SD59x18_ZERO)
        || inDebtVaultUnsettledRealizedDebtUsdX18.gte(SD59x18_ZERO)
) {
    revert Errors.InvalidVaultDebtSettlementRequest();
}
```

Check how function flow will go with data from function description:

In-credit vault:

```solidity
realizedDebt = -100
depositedUSDC = 200
unsettledRealizedDebt = (-100) + (-200) = -300
```

In-debt vault:

```solidity
realizedDebt = 50
depositedUSDC = 10
unsettledRealizedDebt = 50 + (-10) = 40
```

Result:

```solidity
inCreditVaultUnsettledRealizedDebtUsdX18.lte(SD59x18_ZERO) - true
inDebtVaultUnsettledRealizedDebtUsdX18.gte(SD59x18_ZERO) - true
// function will revert
```

But function should not revert with this parameters, vaults should be rebalanced.

CreditDelegationBranch.sol:rebalanceVaultsAssets() does not work as intended and reverts when real in-credit vault needs rebalancing from in-debt vault.

## Proof of Concept

Add this test to test/integration/market-making/credit-delegation-branch/rebalanceVaultsAssets/rebalanceVaultsAssets.t.sol:

```solidity
function testFuzzRevertWhenInvalidVaultDebtSettlementRequestShouldntBeAsInExample(
    uint256 inCreditVaultId,
    uint256 inDebtVaultId
)
    external
    whenTheIndebtVaultAndIncreditVaultsEnginesMatch
{
    VaultConfig memory inCreditVaultConfig = getFuzzVaultConfig(inCreditVaultId);
    VaultConfig memory inDebtVaultConfig = getFuzzVaultConfig(inDebtVaultId);

    vm.assume(inCreditVaultConfig.vaultId != inDebtVaultConfig.vaultId);

    uint128[2] memory vaultIds;

    vaultIds[0] = inCreditVaultConfig.vaultId;
    vaultIds[1] = inDebtVaultConfig.vaultId;

    changePrank({ msgSender: users.owner.account });
    marketMakingEngine.setVaultEngine(inCreditVaultConfig.vaultId, address(1));
    marketMakingEngine.setVaultEngine(inDebtVaultConfig.vaultId, address(1));
    
    // using parameters from example
    marketMakingEngine.workaround_setVaultDebt(inCreditVaultConfig.vaultId, -100);
    marketMakingEngine.workaround_setVaultDepositedUsdc(inCreditVaultConfig.vaultId, 200);

    marketMakingEngine.workaround_setVaultDebt(inDebtVaultConfig.vaultId, 50);
    marketMakingEngine.workaround_setVaultDepositedUsdc(inDebtVaultConfig.vaultId, 10);

    changePrank({ msgSender: address(perpsEngine) });

    // by logic it shouldn't revert but it does
    vm.expectRevert(abi.encodeWithSelector(Errors.InvalidVaultDebtSettlementRequest.selector));

    marketMakingEngine.rebalanceVaultsAssets(vaultIds);
}
```

Run test with command:

```shell
forge test --mt testFuzzRevertWhenInvalidVaultDebtSettlementRequestShouldntBeAsInExample
```

Output:

```shell
Ran 1 test for test/integration/market-making/credit-delegation-branch/rebalanceVaultsAssets/rebalanceVaultsAssets.t.sol:CreditDelegationBranchRebalanceVaultsAssetsIntegration_Test
[PASS] testFuzzRevertWhenInvalidVaultDebtSettlementRequestShouldntBeAsInExample(uint256,uint256) (runs: 1006, μ: 705910, ~: 706406)
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 1.52s (1.49s CPU time)
```

## Recommendation

Change requirement:

```solidity
if (
    inCreditVaultUnsettledRealizedDebtUsdX18.gte(SD59x18_ZERO)
    || inDebtVaultUnsettledRealizedDebtUsdX18.lte(SD59x18_ZERO)
) {
    revert Errors.InvalidVaultDebtSettlementRequest();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerabilityresides in the vault‑rebalance routine of the CreditDelegationBranch contract. The function rebalanceVaultsAssets is designed to move credit from a vault that is in a net‑credit position (negative unsettled realized debt) to a vault that is in a net‑debt position (positive unsettled realized debt). The specification clearly states that the first vault argument must have a negative unsettledRealizedDebt and the second vault argument must have a positive unsettledRealizedDebt. However, the implementation contains a reversed validation check: it reverts when the in‑credit vault’s unsettledRealizedDebt is less than or equal to zero *or* when the in‑debt vault’s unsettledRealizedDebt is greater than or equal to zero. Because the condition uses "lte" for the credit vault and "gte" for the debt vault, the function incorrectly treats the correct state as an error and aborts the transaction.

The root cause is a simple logical inversion of the comparison operators in the guard clause. The developers intended to reject calls where the credit vault is not actually in credit (i.e., its debt is non‑negative) or where the debt vault is not actually in debt (i.e., its debt is non‑positive). Instead, the code checks the opposite, causing legitimate rebalancing attempts to revert. This mistake is subtle because the guard clause looks syntactically plausible and the surrounding comments even note the intended behaviour, making the bug easy to overlook during code review.

When the protocol keeper invokes rebalanceVaultsAssets with two vaults that satisfy the documented pre‑conditions – for example, an in‑credit vault with unsettledRealizedDebt of –300 and an in‑debt vault with unsettledRealizedDebt of +40 – the guard clause evaluates to true and triggers the InvalidVaultDebtSettlementRequest error. As a result, the rebalance does not occur, the credit and debt positions remain mismatched, and the system cannot settle the outstanding obligations. In practice this manifests as a transaction that reverts unexpectedly, leaving users with stuck balances: a user expecting their credit to be transferred to a debt‑bearing vault sees no movement, and the protocol may be unable to honor withdrawals or settlements that depend on a balanced state.

The impact is significant because the rebalancing mechanism is essential for maintaining financial stability across vaults that share the same engine. If rebalancing repeatedly fails, credit may accumulate in some vaults while debt accumulates in others, potentially leading to liquidity shortfalls, delayed settlements, or even a systemic halt of certain market‑making operations. Attackers could deliberately create the vulnerable state (negative credit vault and positive debt vault) to cause a denial‑of‑service condition, preventing keepers from restoring equilibrium.

The issue was discovered during a formal audit by the CodeHawks team, who added a fuzzing test that reproduced the exact scenario described in the documentation. The test confirmed that the function reverts when it should succeed, highlighting the discrepancy between the specification and the implementation. Because the guard clause is evaluated early, the failure appears as a generic “invalid vault debt settlement request” error, which does not immediately reveal that the logic is inverted, making the bug harder to diagnose without reference to the intended semantics.

To remediate the problem, the validation logic must be inverted so that the function reverts only when the in‑credit vault’s unsettledRealizedDebt is *greater than or equal to* zero or when the in‑debt vault’s unsettledRealizedDebt is *less than or equal to* zero. This aligns the runtime check with the documented pre‑conditions and allows legitimate rebalancing operations to proceed. The fix is conceptually a correction of the conditional expression, ensuring that the guard clause enforces the intended sign constraints on the vault debts.

In summary, the bug is a classic case of inverted sign validation in a financial rebalancing routine. It causes legitimate rebalancing transactions to revert, leading to stuck funds, potential liquidity issues, and a denial‑of‑service vector. Correcting the conditional logic restores the intended behaviour and protects the protocol’s accounting integrity.
