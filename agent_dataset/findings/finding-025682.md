---
id: 25682
severity: "Crit/High"
---

# LenderCommitmentGroup_Smart picks the wrong Uniswap price, allowing borrowing at a discount by swapping before withdrawing

## Description



## Proof of Concept

## Vulnerability Detail

`LenderCommitmentGroup_Smart::_getCollateralTokensAmountEquivalentToPrincipalTokens()` is called when calculating the required collateral when taking a loan in `LenderCommitmentGroup_Smart::acceptFundsForAcceptBid()`. In this function, the worst price is supposed to be picked by picking the minimum between `pairPriceWithTwap` and `pairPriceImmediate` when the principal token is `token0` and the maximum when the principal token is `token1`. However, this is incorrect and the logic should be switched.

When the principal token is `token0`, the collateral required is obtained by multiplying the ratio `token1 / token0` by the amount of principal. Thus, the protocol should pick the maximum price such that a bigger amount of collateral is required `collateralAmount = price * principalAmount`, where `price == token1 / token0`. In case the principal token is `token1`, the minimum amount should be picked, as it divides by the price instead.

A poc was carried out where logs were placed to fetch the values of `pairPriceWithTwap`, `pairPriceImmediate`, `worstCasePairPrice` and `collateralTokensAmountToMatchValue` confirming that the best price for the borrower is picked. Insert the following test in the test file pasted in issue 'Drained lender due to LenderCommitmentGroup_Smart::acceptFundsForAcceptBid() _collateralAmount by STANDARD_EXPANSION_FACTOR multiplication' and place the mentioned logs to confirm the behaviour:

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

## Impact

As the borrower gets the best price, it may do a flashloan on another pool, swap in the pool that the `LenderCommitmentGroup_Smart` is using to manipulate the ratio and get principal almost for free and then repay the flashloan, stealing the funds from LPs.

## Code Snippet

[LenderCommitmentGroup_Smart::_getCollateralTokensAmountEquivalentToPrincipalTokens()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L634>).

```solidity
function _getCollateralTokensAmountEquivalentToPrincipalTokens(
    uint256 principalTokenAmountValue,
    uint256 pairPriceWithTwap,
    uint256 pairPriceImmediate,
    bool principalTokenIsToken0
) internal view returns (uint256 collateralTokensAmountToMatchValue) {
    if (principalTokenIsToken0) {
        //token 1 to token 0 ?
        uint256 worstCasePairPrice = Math.min( //@audit is incorrect. should be max
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

## Recommendation

Switch the `min` and `max` usage in `LenderCommitmentGroup_Smart::_getCollateralTokensAmountEquivalentToPrincipalTokens()`.

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
