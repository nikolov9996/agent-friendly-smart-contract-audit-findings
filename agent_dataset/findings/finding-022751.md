---
id: 22751
severity: "High"
---

# LenderCommitmentGroup_Smart picks the wrong price

## Description

LenderCommitmentGroup_Smart calculates the spot and twap prices of the Uniswap pool and ideally picks the worst price for the user, but this is not the case and the opposite is true. LenderCommitmentGroup_Smart::_getCollateralTokensAmountEquivalentToPrincipalTokens() is called when calculating the required collateral when taking a loan in LenderCommitmentGroup_Smart::acceptFundsForAcceptBid(). In this function, the worst price is supposed to be picked by picking the minimum between pairPriceWithTwap and pairPriceImmediate when the principal token is token0 and the maximum when the principal token is token1. However, this is incorrect and the logic should be switched. When the principal token is token0, the collateral required is obtained by multiplying the ratio token1 / token0 by the amount of principal. Thus, the protocol should pick the maximum price such that a bigger amount of collateral is required collateralAmount = price * principalAmount, where price == token1 / token0. In case the principal token is token1, the minimum amount should be picked, as it divides by the price instead. A poc was carried out where logs were placed to fetch the values of pairPriceWithTwap, pairPriceImmediate, worstCasePairPrice and collateralTokensAmountToMatchValue confirming that the best price for the borrower is picked. Insert the following test in the test file pasted in issue 'Drained lender due to LenderCommitmentGroup_Smart::acceptFundsForAcceptBid() _collateralAmount by STANDARD_EXPANSION_FACTOR multiplication' and place the mentioned logs to confirm the behaviour:
```solidity
function test_POC_wrongUniswapPricePicked() public {
    uint256 principalAmount = 1e18;
    deal(address(DAI), user, principalAmount);
    vm.startPrank(user);
    // add principal to lender to get shares
    DAI.approve(address(lender), principalAmount);
    uint256 shares = lender.addPrincipalToCommitmentGroup(principalAmount, user);
    // approve the forwarder
    tellerV2.approveMarketForwarder(marketId, address(smartCommitmentForwarder));
    // borrow the principal
    uint256 collateralAmount = 1e18;
    deal(address(WETH), user, collateralAmount);
    WETH.approve(address(collateralManager), collateralAmount);
    uint256 bidId = smartCommitmentForwarder.acceptCommitmentWithRecipient(
        address(lender),
        principalAmount,
        collateralAmount,
        0,
        address(WETH),
        user,
        0,
        2 days
    );
    vm.stopPrank();
}
```
As the borrower gets the best price, it may do a flashloan on another pool, swap in the pool that the LenderCommitmentGroup_Smart is using to manipulate the ratio and get principal almost for free and then repay the flashloan, stealing the funds from LPs.
```solidity
function _getCollateralTokensAmountEquivalentToPrincipalTokens(
    uint256 principalTokenAmountValue,
    uint256 pairPriceWithTwap,
    uint256 pairPriceImmediate,
    bool principalTokenIsToken0
) internal view returns (uint256 collateralTokensAmountToMatchValue) {
    if (principalTokenIsToken0) {
        //token 1 to token 0 ?
        uint256 worstCasePairPrice = Math.min(
            pairPriceWithTwap,
            pairPriceImmediate
        );
        collateralTokensAmountToMatchValue = token1ToToken0(
            principalTokenAmountValue,
            worstCasePairPrice //if this is lower, collateral tokens amt will be higher
        );
    } else {
        //token 0 to token 1 ?
        uint256 worstCasePairPrice = Math.max(
            pairPriceWithTwap,
            pairPriceImmediate
        );
        collateralTokensAmountToMatchValue = token0ToToken1(
            principalTokenAmountValue,
            worstCasePairPrice //if this is lower, collateral tokens amt will be higher
        );
    }
}
```

## Proof of Concept

no poc

## Recommendation

Switch the min and max usage in LenderCommitmentGroup_Smart::_getCollateralTokensAmountEquivalentToPrincipalTokens().
```solidity
function _getCollateralTokensAmountEquivalentToPrincipalTokens(
    uint256 principalTokenAmountValue,
    uint256 pairPriceWithTwap,
    uint256 pairPriceImmediate,
    bool principalTokenIsToken0
) internal view returns (uint256 collateralTokensAmountToMatchValue) {
    if (principalTokenIsToken0) {
        //token 1 to token 0 ?
        uint256 worstCasePairPrice = Math.max(
            pairPriceWithTwap,
            pairPriceImmediate
        );
        collateralTokensAmountToMatchValue = token1ToToken0(
            principalTokenAmountValue,
            worstCasePairPrice //if this is lower, collateral tokens amt will be higher
        );
    } else {
        //token 0 to token 1 ?
        uint256 worstCasePairPrice = Math.min(
            pairPriceWithTwap,
            pairPriceImmediate
        );
        collateralTokensAmountToMatchValue = token0ToToken1(
            principalTokenAmountValue,
            worstCasePairPrice //if this is lower, collateral tokens amt will be higher
        );
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect worst‑case price selection in the function that computes the amount of collateral required for a loan. The contract is supposed to protect lenders by using the most unfavorable price from a Uniswap pool – the minimum price when the loan principal is token0 and the maximum price when the principal is token1 – so that the borrower must provide the largest possible amount of collateral. The implementation mistakenly uses Math.min for token0 and Math.max for token1, which actually selects the most favorable price for the borrower. As a result the calculated collateral amount is lower than it should be. This mis‑calculation can be exploited by a borrower who first obtains a flash‑loan, manipulates the pool price, and then borrows from the LenderCommitmentGroup_Smart contract with insufficient collateral, effectively receiving principal for near‑zero cost and leaving the lender under‑collateralized. The impact is that the lender’s collateral pool can be drained, LPs in the referenced Uniswap pool lose value, and the protocol’s accounting assumptions about over‑collateralisation are violated. The bug manifests whenever acceptFundsForAcceptBid() is called, i.e., when a borrower accepts a loan commitment, and the price oracle returns a spot price and a TWAP price. Users see the loan succeed but the required collateral appears normal, while the lender later discovers that the collateral balance is insufficient or that the loan was repaid with far less value than expected. The issue was discovered during a security audit by Sherlock, who added logging to the price variables and observed that the worstCasePairPrice variable actually held the best price for the borrower. The problem is subtle because the code comments claim a worst‑case price is being used, and the min/max functions are syntactically correct, making the logical error easy to miss. The proper fix is to invert the use of Math.min and Math.max: when the principal token is token0 the contract should take the maximum of the TWAP and immediate price, and when the principal token is token1 it should take the minimum. This change restores the intended over‑collateralisation guarantee and prevents borrowers from exploiting price manipulation to drain funds.
