---
id: 3678
severity: "High"
---

# Borrower can bypass maxLoanRatio's configuration of a pool via buyLoan()

## Description

In buyLoan(), there is no validation if the loanRatio < pool.maxLoanRatio. Therefore, a lender can be given a loan with higher LTV than his pool which he doesn't want at all.

Since buyLoan() can be called by anyone, a malicious borrower can borrow a loan from his own pool with a pretty high maxLoanRatio so that he can put the least collateral possible to take the loan, then forcefully push this loan by calling buyLoan() with his own loan to a random pool with enough pool balance of the pairs. Doing this helps the borrower avoid the risk of high LTV.
Borrower can give his high LTV loan to any pool with enough balance by calling buyLoan() to escape the risk of high LTV.
Anyone or the new lender himself/herself can buy the loan via buyLoan() without noticing the high LTV in it, which may lead to fund losing.

## Proof of Concept

We mint the loanToken to borrower so that he can set up his pool in setUp() function of Lender.t.sol
```diff
loanToken.mint(address(borrower), 100000 * 10 ** 18);
```
Paste this code into Lender.t.sol: https://github.com/Cyfrin/2023-07-beedle/blob/main/test/Lender.t.sol.
Right here the borrower set up his pool with very high maxLoanRatio of 5 and borrow the loan himself/herself.

```solidity
function test_borrowPoc() public {
    vm.startPrank(borrower);
    Pool memory p = Pool({
        lender: borrower,
        loanToken: address(loanToken),
        collateralToken: address(collateralToken),
        minLoanSize: 100 * 10 ** 18,
        poolBalance: 1000 * 10 ** 18,
        maxLoanRatio: 5 * 10 ** 18,
        auctionLength: 1 days,
        interestRate: 1000,
        outstandingLoans: 0
    });
    bytes32 poolId = lender.setPool(p);

    (, , , , uint256 poolBalance, , , , ) = lender.pools(poolId);
    assertEq(poolBalance, 1000 * 10 ** 18);

    Borrow memory b = Borrow({
        poolId: poolId,
        debt: 100 * 10 ** 18,
        collateral: 100 * 10 ** 18
    });
    Borrow[] memory borrows = new Borrow[](1);
    borrows[0] = b;
    lender.borrow(borrows);

    assertEq(collateralToken.balanceOf(address(lender)), 100 * 10 ** 18);
    (, , , , poolBalance, , , , ) = lender.pools(poolId);
    assertEq(poolBalance, 900 * 10 ** 18);
}
```
Paste this code into Lender.t.sol: https://github.com/Cyfrin/2023-07-beedle/blob/main/test/Lender.t.sol.
Right here the borrower starts the auction for his loan and call buyLoan() with the pool of lender1, which only has the maxLoanRatio value of 1. The test goes through successfully, meaning the loan is bought to the new pool and the borrower can now enjoy his high LTV loan being managed by the new pool (lender1)

```solidity
function test_bypassMaxLoanRatio() public {
    test_borrowPoc();
    // accrue interest
    vm.warp(block.timestamp + 1 days);
    // kick off auction
    vm.startPrank(borrower);

    uint256[] memory loanIds = new uint256[](1);
    loanIds[0] = 0;

    lender.startAuction(loanIds);

    vm.startPrank(lender1);
    Pool memory p = Pool({
        lender: lender1,
        loanToken: address(loanToken),
        collateralToken: address(collateralToken),
        minLoanSize: 100 * 10 ** 18,
        poolBalance: 1000 * 10 ** 18,
        maxLoanRatio: 1 * 10 ** 18,
        auctionLength: 1 days,
        interestRate: 1000,
        outstandingLoans: 0
    });
    bytes32 poolId = lender.setPool(p);

    // warp to middle of auction
    vm.warp(block.timestamp + 12 hours);

    vm.startPrank(borrower);

    lender.buyLoan(0, poolId);
}
```
Use forge test --mt test_bypassMaxLoanRatio to run this test case.

## Recommendation

Consider implement a validation for the loan ratio like other functions in the contract after line 485.
```diff
485      uint256 totalDebt = loan.debt + lenderInterest + protocolInterest;
uint256 loanRatio = (totalDebt * 10 ** 18) / loan.collateral;
if (loanRatio > pools[poolId].maxLoanRatio) revert RatioTooHigh();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is a missing business‑logic validation in the buyLoan function of the lending protocol. When a loan is purchased from an auction, the contract calculates the loan‑to‑value ratio (loanRatio) but does not verify that this ratio is lower than the maxLoanRatio configured for the destination pool. As a result, a borrower can create a personal pool with an artificially high maxLoanRatio, borrow a loan using minimal collateral, start an auction, and then call buyLoan to transfer the loan to any other pool that has a lower maxLoanRatio. Because the buyLoan function lacks the ratio check that other functions enforce, the destination pool accepts the loan even though its LTV exceeds the pool’s risk parameters. This bypass can be performed by any caller, not only the borrower, so a lender may unknowingly acquire a high‑risk loan and suffer unexpected losses, such as collateral being insufficient to cover the debt or the loan being liquidated prematurely. The vulnerability manifests whenever buyLoan is invoked, regardless of the caller, and when the loan’s computed ratio exceeds the pool’s configured limit. It affects borrowers who can exploit the flaw, lenders who may receive loans with unacceptable risk, and the overall protocol integrity because accounting assumptions about loan safety are violated. The flaw was discovered during a security audit by CodeHawks through a crafted test case that minted a loan token, set up a pool with maxLoanRatio of five, borrowed with a 1:1 collateral‑debt ratio, and then successfully moved the loan to another pool with maxLoanRatio of one without any revert. The problem is subtle because the UI and transaction receipts show a successful loan purchase, and there is no explicit warning about the high LTV, making it hard for users to notice the discrepancy. To remediate, the contract should perform the same ratio validation used elsewhere: after computing loanRatio, compare it to pools[poolId].maxLoanRatio and revert with a RatioTooHigh error if the loan exceeds the allowed limit. This correction restores the intended risk controls and prevents borrowers from bypassing pool‑level LTV constraints, thereby protecting lenders from unexpected fund loss.
