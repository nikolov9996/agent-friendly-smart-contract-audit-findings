---
id: 2999
severity: "High"
---

# Reentrancy during migration allows for unauthorized access in receiveFlashLoan()

## Description

OriginationControllerMigrate.migrateV3Loan() has a whenBorrowerReset modifier that resets the borrower cache after the migration function completes. This is a measure to prevent external actors from initiating a flash loan with malicious data and targeting OriginationControllerMigrate.receiveFlashLoan().
```solidity
function receiveFlashLoan(
    IERC20[] calldata assets,
    uint256[] calldata amounts,
    uint256[] calldata feeAmounts,
    bytes calldata params
) external nonReentrant {
    if (msg.sender != VAULT) revert OCM_UnknownCaller(msg.sender, VAULT);
    OriginationLibrary.OperationData memory opData = abi.decode(params, (OriginationLibrary.OperationData));
    // verify this contract started the flash loan
    if (opData.borrower != borrower) revert OCM_UnknownBorrower(opData.borrower, borrower);
    // borrower must be set
    if (borrower == address(0)) revert OCM_BorrowerNotCached();
    _executeOperation(assets, amounts, feeAmounts, opData);
}
```
The problem in OriginationControllerMigrate.migrateV3Loan() is that after OriginationControllerMigrate._initiateFlashLoan() finishes execution, the flash loan cycle that starts from Balancer.flashLoan() has already concluded and the reentrancy guards are unlocked.
However, execution continues in OriginationControllerMigrate._initializeMigrationLoan(), which will make a call to LoanCore.startLoan(), which then safe mints ERC721 PromissoryNotes to the lender and borrower for the new (migrated) loan.
At this point, the borrower or lender can utilize the onERC721Received hook external call, during which they can initiate new flash loans through Balancer.flashLoan() with arbitrary data that targets OriginationControllerMigrate.receiveFlashLoan(), which won't revert since the borrower cache hasn't yet been reset by the whenBorrowerReset modifier.
The issue now is that OriginationControllerMigrate._executeOperation() can be called with arbitrary data, which can lead to impacts such as theft of funds from anyone who has approval towards OriginationControllerMigrate and abusing safeApprove() to permanently lock OriginationControllerMigrate.migrateV3Loan().
```solidity
function migrateV3Loan()
    external
    override
    whenNotPaused
    whenBorrowerReset
{
    // code ...
    // @note borrower cache gets set in _initiateFlashLoan()
    if (flashLoanTrigger) {
        _initiateFlashLoan(oldLoanId, newTerms, msg.sender, lender, amounts);
    }
    // code ...
    // borrower cache is not reset yet
    _initializeMigrationLoan(newTerms, msg.sender, lender, amounts.amountFromLender, amounts.amountToBorrower);
    // code ...
}
```

## Proof of Concept

no poc

## Recommendation

An alternative fix to the one below is to add nonReentrant modifier to OriginationControllerMigrate._initiateFlashLoan(), however, the borrower cache would still remain initialized during OriginationControllerMigrate.migrateV3Loan(), even after the flash loan has been executed.
```solidity
);
// Flash loan based on principal + interest
IVault(VAULT).flashLoan(this, assets, amounts, params);
borrower = address(0);
}
/**
 * @notice Callback function for flash loan. OpData is decoded and used to
 * execute the migration.
 *
```
```solidity
*/
modifier whenBorrowerReset() {
    if (borrower != address(0)) revert OCM_BorrowerNotReset(borrower);
    _;
    borrower = address(0);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw that appears during the migration of a loan when the contract executes a flash‑loan followed by the minting of ERC‑721 promissory‑note tokens. The migration function sets a temporary borrower cache before calling the flash‑loan helper, and a whenBorrowerReset modifier is supposed to clear that cache only after the whole migration finishes. However, the flash‑loan callback (receiveFlashLoan) is protected by a nonReentrant guard that is released as soon as the Balancer.flashLoan call returns. The migration routine then continues to mint the ERC‑721 token, which triggers an external onERC721Received hook on the borrower or lender contract. Because the borrower cache has not yet been cleared, the attacker can invoke a new flash loan from within that hook, passing arbitrary parameters that reach receiveFlashLoan. The receiveFlashLoan function only checks that the caller is the vault and that the borrower field matches the cached value; it does not verify that the cache has been reset. Consequently, the attacker can execute _executeOperation with crafted data, potentially moving assets, abusing safeApprove, or permanently locking the migrateV3Loan function. The impact is loss of funds for any user who has granted approval to the migration contract, disruption of loan migration, and the possibility of a denial‑of‑service condition. The bug manifests only while migrateV3Loan is in progress, after the flash‑loan completes but before the whenBorrowerReset modifier runs its post‑condition. It affects borrowers, lenders, and the protocol itself because the migration logic is central to loan upgrades. The issue was discovered during a manual audit that traced the control flow of the migration function and identified that the reentrancy guard was lifted too early. It is subtle because the receiveFlashLoan function appears safe when examined in isolation, and the nonReentrant modifier gives a false sense of protection. To remediate, the borrower cache should be cleared before any external call that could trigger reentrancy, the flash‑loan initiation should be wrapped with its own nonReentrant guard, or the minting of the ERC‑721 token should be moved after the cache reset. In general, the pattern belongs to the class of “reentrancy after state reset” bugs where a contract’s internal state is left vulnerable during a multi‑step operation that includes external calls.
