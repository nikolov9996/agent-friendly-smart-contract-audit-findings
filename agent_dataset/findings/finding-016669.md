---
id: 16669
severity: "High"
---

# `MIMOEmptyVault.sol executeOperation`

## Description

`MIMOEmptyVault.sol executeAction()` is supposed to pay off the debt and return the leftover assets to the owner of the Vault. But in fact the emptyVault contract, after executing the executionOperation(), only pays back the flash loan, and does not transfer the leftover assets to the owner, and locked in the emptyVault contract.

## Proof of Concept

```solidity
function executeOperation(
    address[] calldata assets,
    uint256[] calldata amounts,
    uint256[] calldata premiums,
    address initiator,
    bytes calldata params
) external override returns (bool) {

    ....
    ....

    require(flashloanRepayAmount <= vaultCollateral.balanceOf(address(this)), Errors.CANNOT_REPAY_FLASHLOAN);

    vaultCollateral.safeIncreaseAllowance(address(lendingPool), flashloanRepayAmount);

    //****Paid off the flash loan but did not transfer the remaining balance back to mimoProxy or owner ***//

    return true;
}
```

Add logs to test case

test/02_integration/MIMOEmtpyVault.test.ts

```solidity
it("should be able to empty vault with 1inch", async () => {
    ...
    ...
    ...
    console.log("before emptyVault balance:--->", (await wmatic.balanceOf(emptyVault.address)) + "");
    const tx = await mimoProxy.execute(emptyVault.address, MIMOProxyData);
    const receipt = await tx.wait(1);
    console.log("after emptyVault balance: --->", (await wmatic.balanceOf(emptyVault.address)) + "");
```

print:

    before emptyVault balance:---> 0
    after emptyVault balance: ---> 44383268870065355782

## Recommendation

```solidity
function executeOperation(
    address[] calldata assets,
    uint256[] calldata amounts,
    uint256[] calldata premiums,
    address initiator,
    bytes calldata params
) external override returns (bool) {

    ....
    ....

    require(flashloanRepayAmount <= vaultCollateral.balanceOf(address(this)), Errors.CANNOT_REPAY_FLASHLOAN);

    vaultCollateral.safeIncreaseAllowance(address(lendingPool), flashloanRepayAmount);

    //****transfer the remaining balance back to mimoProxy or owner ***//
    vaultCollateral.safeTransfer(address(mimoProxy), vaultCollateral.balanceOf(address(this)) - flashloanRepayAmount);

    return true;
}
```

We confirm this is a vulnerability and intend to fix this - only the amount needed to repay the flashloan should be transferred from the `MimoProxy` to the `MIMOEmptyVault` action contract.

**horsefacts (warden) reviewed mitigation:**

**Status:** ✅ Resolved

**Finding:** Wardens identified that `MIMOEmptyVault` transferred in a vault’s full collateral balance when repaying vault rebalance flash loans, but did not return excess collateral to the vault owner when the flash loan repayment amount was less than the vault’s collateral balance. Instead, the excess amount would be locked in the action contract.

**What changed:** The Mimo team updated `MIMOEmptyVault#emptyVaultOperation` to transfer collateral exactly equal to the [flashloan repayment amount](https://github.com/mimo-capital/2022-08-mimo/blob/5186ef4be23f9dda81c8474096edb1f0594d70c3/contracts/actions/MIMOEmptyVault.sol#L142), rather than the full vault balance. This behavior is demonstrated by an [integration test](https://github.com/mimo-capital/2022-08-mimo/blob/5186ef4be23f9dda81c8474096edb1f0594d70c3/test/02_integration/MIMOEmtpyVault.test.ts#L297).

**Why it works:** Since excess collateral is never transferred to `MIMOEmptyVault`, it can no longer be locked in the contract.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the empty‑vault action contract of the MIMO protocol, specifically in the function that executes a flash‑loan‑based rebalance (executeOperation). The function is intended to repay the flash loan and then return any surplus collateral to the vault owner or to the MIMOProxy that orchestrates the operation. However, after satisfying the flash‑loan repayment, the implementation does not perform any transfer of the remaining token balance. Instead, it simply returns true, leaving the surplus tokens locked inside the action contract. The root cause is a logical omission: the contract increases the allowance for the lending pool to cover the exact repayment amount but never moves the excess collateral out of its own address. This can be exploited whenever the flash‑loan repayment amount is lower than the total collateral held by the vault, which is a normal situation when the vault contains more assets than necessary to cover the debt. An attacker does not need to craft special inputs; any user who invokes the empty‑vault operation under these conditions will see the leftover assets become inaccessible. The impact is that funds that should be returned to the user disappear from their wallet and are trapped in the contract, effectively causing a loss of collateral. The issue manifests only when the empty‑vault action is called with a flash‑loan repayment that does not consume the full vault balance—i.e., when the vault holds surplus collateral after the debt is cleared. The affected parties are the vault owners, delegators, and any participants relying on the protocol to safely return their assets after a rebalance. The bug was discovered during a security audit and reproduced with an integration test that logged the contract’s balance before and after the operation, revealing a non‑zero balance remaining in the contract despite a successful transaction. The problem is subtle because the transaction does not revert, emits no error, and the UI may simply show a successful empty‑vault call, making it easy to overlook the missing funds. To remediate the issue the contract should be modified to transfer exactly the amount needed to repay the flash loan to the lending pool and then explicitly send the residual token balance back to the vault owner or to the MIMOProxy. In abstract terms, the bug belongs to the class of asset‑leakage errors caused by incomplete post‑operation fund redistribution, violating the business logic that all collateral must either service the debt or be returned to the rightful owner.
