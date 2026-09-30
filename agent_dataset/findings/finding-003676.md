---
id: 3676
severity: "High"
---

# During refinance() new Pool balance debt is subtracted twice

## Description

A borrower has the opportunity to move their loan to another pool under new lending conditions.

During refinancing interest from the loan is transferred to the old pool.

The debt is then transferred to the new pool however this subtraction occurs twice, resulting in loss of funds to the Lenders pool.

In refinance() the debt to the new pool is transferred at line 636

```solidity
_updatePoolBalance(poolId, pools[poolId].poolBalance - debt);
```

The debt is subtracted again at line 696

```solidity
pools[poolId].poolBalance -= debt;
```

## Proof of Concept

```solidity
function test_Refinance() public {
    vm.startPrank(lender1);
    Pool memory p1 = Pool({
        lender: lender1,
        loanToken: address(loanToken),
        collateralToken: address(collateralToken),
        minLoanSize: 100 * 10 ** 18,
        poolBalance: POOLLOANTOKEN_BALANCE,
        maxLoanRatio: 2 * 10 ** 18,
        auctionLength: 1 days,
        interestRate: 1000,
        outstandingLoans: 0
    });

    Pool memory p2 = Pool({
        lender: lender2,
        loanToken: address(loanToken),
        collateralToken: address(collateralToken),
        minLoanSize: 100 * 10 ** 18,
        poolBalance: POOLBLOANTOKENBALANCE,
        maxLoanRatio: 2 * 10 ** 18,
        auctionLength: 1 days,
        interestRate: 1000,
        outstandingLoans: 0
    });

    bytes32 poolIdOne = lender.setPool(p1);

    vm.startPrank(lender2);
    bytes32 poolIdTwo = lender.setPool(p2);

    bytes32[] memory poolIds = new bytes32[](2);
    poolIds[0] = poolIdOne;
    poolIds[1] = poolIdTwo;

    uint256[] memory loansIds = new uint256[](1);
    loansIds[0] = 0;

    vm.startPrank(borrower);
    Borrow memory b = Borrow({poolId: poolIdOne, debt: LOAN_AMOUNT, collateral: 1000 * 10 ** 18});
    Borrow[] memory borrows = new Borrow[](1);
    borrows[0] = b;
    lender.borrow(borrows);

    Refinance memory r =
        Refinance({loanId: 0, poolId: poolIdTwo, debt: 1000 * 10 ** 18, collateral: 1000 * 10 ** 18});
    Refinance[] memory refinances = new Refinance[](1);
    refinances[0] = r;

    vm.warp(10 days);

    // New Pool balance before refinancing
    (,,,, uint256 poolBalance,,,,) = lender.pools(poolIdTwo);
    assertEq(poolBalance, (POOLBLOANTOKENBALANCE));

    lender.refinance(refinances);

    (,,,, poolBalance,,,,) = lender.pools(poolIdTwo);
    // Debt is transferred to new pool twice
    assertEq(poolBalance, (POOLBLOANTOKENBALANCE) - (2 * 1000 * 10 ** 18));
}
```

## Recommendation

No data

## Derived Narrative

The following field is derived content and may not be source-grounded:

During the refinance operation a borrower can move an existing loan from one liquidity pool to another with different lending terms. The contract first transfers the accrued interest from the loan back to the original pool, then attempts to transfer the outstanding debt amount to the target pool by decreasing the target pool's balance. However the implementation subtracts the debt amount from the target pool's balance twice: once through an internal helper call that updates the pool balance, and a second time by directly reducing the stored poolBalance variable. As a result the target pool's recorded balance is reduced by twice the debt, effectively removing funds that should belong to the lenders of that pool. The bug manifests whenever a refinance is executed, i.e., after the loan has accrued interest and the borrower calls refinance with a new pool identifier. Any borrower who successfully refinances a loan triggers the double subtraction, causing the lenders' pool to lose the amount of the transferred debt. From a user perspective the lenders see their pool balance drop unexpectedly, sometimes to zero, and borrowers may notice that the new pool reports a lower balance than expected, leading to missing funds for future borrowers. The issue was discovered during a manual audit and reproduced with a unit test that checks the pool balance before and after refinance, showing a discrepancy of two times the debt. The problem is subtle because the two statements appear in different parts of the function and both appear to be legitimate balance updates, making it easy to miss during code review. The vulnerability belongs to the class of accounting bugs where state variables are updated redundantly, causing double counting or double subtraction. To fix the issue the contract should ensure that the debt transfer updates the pool balance exactly once, either by using the helper function exclusively or by removing the direct subtraction, and adding a test that validates that the pool balance changes by exactly the debt amount. Proper invariant checks on pool balances before and after refinance would also help detect similar errors.
