---
id: 21533
severity: "High"
---

# The collateral remainder cap is incorrectly calculated during liquidation

## Description

When a position is overdue, it can be liquidated even if the owner has a sufficient collateral ratio. Some rewards are sent to the liquidator as an incentive and some fees are assigned to the protocol. However, the calculation of the protocol fee is flawed due to an incorrect collateral remainder cap calculation.

Imagine the collateral ratio for liquidation is set at 130%. The collateral equivalent to the debt should be paid to the protocol, and the excess collateral (30%) can be the remainder cap. Currently, the entire 130% is treated as the remainder cap, leading to an unfair situation where a user with a 150% collateral ratio experiences more loss than a user with a 140% CR.

This discourages users with higher CRs, who generally contribute to the protocol’s health. If higher CRs result in greater losses, it disincentivizes users from providing sufficient collateral to the protocol.

## Proof of Concept

Imagine Bob and Candy have the same debt position, and these positions are overdue.

  * The collateral ratio for liquidation is 130%.
  * Candy has a 150% collateral ratio, and Bob has a 140% CR.

Both positions are liquidated by liquidators:

```solidity
function executeLiquidate(State storage state, LiquidateParams calldata params)
    external
    returns (uint256 liquidatorProfitCollateralToken)
{
    DebtPosition storage debtPosition = state.getDebtPosition(params.debtPositionId);
    LoanStatus loanStatus = state.getLoanStatus(params.debtPositionId);
    uint256 collateralRatio = state.collateralRatio(debtPosition.borrower)

    uint256 collateralProtocolPercent = state.isUserUnderwater(debtPosition.borrower)
        ? state.feeConfig.collateralProtocolPercent
        : state.feeConfig.overdueCollateralProtocolPercent;

    uint256 assignedCollateral = state.getDebtPositionAssignedCollateral(debtPosition);  // @1
    uint256 debtInCollateralToken = state.debtTokenAmountToCollateralTokenAmount(debtPosition.futureValue); // @2
    uint256 protocolProfitCollateralToken = 0;

    // profitable liquidation
    if (assignedCollateral > debtInCollateralToken) {
        uint256 liquidatorReward = Math.min(
            assignedCollateral - debtInCollateralToken,
            Math.mulDivUp(debtPosition.futureValue, state.feeConfig.liquidationRewardPercent, PERCENT)
        );  // @3
        liquidatorProfitCollateralToken = debtInCollateralToken + liquidatorReward;  

        // split the remaining collateral between the protocol and the borrower, capped by the crLiquidation
        uint256 collateralRemainder = assignedCollateral - liquidatorProfitCollateralToken;  // @4

        // cap the collateral remainder to the liquidation collateral ratio
        //   otherwise, the split for non-underwater overdue loans could be too much
        uint256 cllateralRemainderCap =
            Math.mulDivDown(debtInCollateralToken, state.riskConfig.crLiquidation, PERCENT);  // @5

        collateralRemainder = Math.min(collateralRemainder, collateralRemainderCap);

        protocolProfitCollateralToken = Math.mulDivDown(collateralRemainder, collateralProtocolPercent, PERCENT);  // @6
    } 
}
```

`@1`: Calculate assigned collaterals to the debt position. The amount assigned from Candy’s collateral is larger than that from Bob’s.  
`@2`: Convert the debt token to the collateral token. The converted amounts are the same for both users.  
`@3`: Calculate the reward for liquidation. These amounts are the same because the debt sizes are the same and both users have enough CR to cover the profit.  
`@4`: Calculate the collateral remainder. Candy obviously has a larger amount.  
`@5`: Calculate the collateral remainder cap. The cap should be 30%, but it is currently calculated as 130%, which is the CR for liquidation itself.  
`@6`: As a result, Candy will experience more loss than Bob due to their excess amounts (50%, 40%) being below the cap (130%).

If users know that they will experience more loss when they have a larger CR, they will tend to maintain their CR as low as possible. While they will try to avoid liquidation, there will be no users with a CR higher than, for example, 200%. This is detrimental to the protocol.

Please check below log:
    
      future value of Bob   =>  60000000
      future value of Candy =>  60000000
      assigned collateral of Bob   =>  100000000000000000000
      assigned collateral of Candy =>  120000000000000000000
      debt in collateral token of Bob   =>  60000000000000000000
      debt in collateral token of Candy =>  60000000000000000000
      liquidator reward of Bob    =>  3000000
      liquidator reward of Candy  =>  3000000
      liquidator profit of collateral token of Bob    =>  60000000000003000000
      liquidator profit of collateral token of Candy  =>  60000000000003000000
      collateral remainder of Bob    =>  39999999999997000000
      collateral remainder of Candy  =>  59999999999997000000
      collateral remainder cap of Bob    =>  78000000000000000000
      collateral remainder cap of Candy  =>  78000000000000000000
      collateral remainder of Bob    =>  39999999999997000000
      collateral remainder of Candy  =>  59999999999997000000
      protocol profit collateral token of Bob    =>  399999999999970000
      protocol profit collateral token of Candy  =>  599999999999970000

Please add below test to the `test/local/actions/Liquidate.t.sol`: (use `--var-ir` flag):

```solidity
function test_liquidate_protocol_profit() public {
    _deposit(alice, usdc, 300e6);
    _deposit(bob, weth, 100e18);
    _deposit(candy, weth, 120e18);
    _deposit(liquidator, weth, 1000e18);
    _deposit(liquidator, usdc, 1000e6);

    _buyCreditLimit(alice, block.timestamp + 365 days, YieldCurveHelper.pointCurve(365 days, 0.03e18));

    uint256 debtPositionIdOfBob = _sellCreditMarket(bob, alice, RESERVED_ID, 60e6, 365 days, true);
    uint256 debtPositionIdOfCandy = _sellCreditMarket(candy, alice, RESERVED_ID, 60e6, 365 days, true);

    vm.warp(block.timestamp + 365 days + 1 days);
    // 1 WETH = 1 USDC for test
    _setPrice(1e18);  

    // loan is not underwater, but it's overdue
    uint256 collateralProtocolPercent = size.feeConfig().overdueCollateralProtocolPercent;

    uint256 futureValueOfBob = size.getDebtPosition(debtPositionIdOfBob).futureValue;
    uint256 futureValueOfCandy = size.getDebtPosition(debtPositionIdOfCandy).futureValue;
    console2.log('future value of Bob   => ', futureValueOfBob);
    console2.log('future value of Candy => ', futureValueOfCandy);

    // uint256 assignedCollateral = state.getDebtPositionAssignedCollateral(debtPosition); (Line 90)
    uint256 assignedCollateralOfBob = size.getDebtPositionAssignedCollateral(debtPositionIdOfBob);
    uint256 assignedCollateralOfCandy = size.getDebtPositionAssignedCollateral(debtPositionIdOfCandy);
    console2.log('assigned collateral of Bob   => ', assignedCollateralOfBob);
    console2.log('assigned collateral of Candy => ', assignedCollateralOfCandy);

    // uint256 debtInCollateralToken = state.debtTokenAmountToCollateralTokenAmount(debtPosition.futureValue); (Line 91)
    uint256 debtInCollateralTokenOfBob = size.debtTokenAmountToCollateralTokenAmount(futureValueOfBob);
    uint256 debtInCollateralTokenOfCandy = size.debtTokenAmountToCollateralTokenAmount(futureValueOfCandy);
    console2.log('debt in collateral token of Bob   => ', debtInCollateralTokenOfBob);
    console2.log('debt in collateral token of Candy => ', debtInCollateralTokenOfCandy);

    // Line 96
    uint256 liquidatorRewardOfBob = Math.min(
        assignedCollateralOfBob - debtInCollateralTokenOfBob,
        Math.mulDivUp(futureValueOfBob, size.feeConfig().liquidationRewardPercent, PERCENT)
    );
    uint256 liquidatorRewardOfCandy = Math.min(
        assignedCollateralOfCandy - debtInCollateralTokenOfCandy,
        Math.mulDivUp(futureValueOfCandy, size.feeConfig().liquidationRewardPercent, PERCENT)
    );
    console2.log('liquidator reward of Bob    => ', liquidatorRewardOfBob);
    console2.log('liquidator reward of Candy  => ', liquidatorRewardOfCandy);

    // liquidatorProfitCollateralToken = debtInCollateralToken + liquidatorReward; (Line 100)
    uint256 liquidatorProfitCollateralTokenOfBob = debtInCollateralTokenOfBob + liquidatorRewardOfBob;
    uint256 liquidatorProfitCollateralTokenOfCandy = debtInCollateralTokenOfCandy + liquidatorRewardOfCandy;
    console2.log('liquidator profit of collateral token of Bob    => ', liquidatorProfitCollateralTokenOfBob);
    console2.log('liquidator profit of collateral token of Candy  => ', liquidatorProfitCollateralTokenOfCandy);

    // uint256 collateralRemainder = assignedCollateral - liquidatorProfitCollateralToken; (Line 103)
    uint256 collateralRemainderOfBob = assignedCollateralOfBob - liquidatorProfitCollateralTokenOfBob;
    uint256 collateralRemainderOfCandy = assignedCollateralOfCandy - liquidatorProfitCollateralTokenOfCandy;
    console2.log('collateral remainder of Bob    => ', collateralRemainderOfBob);
    console2.log('collateral remainder of Candy  => ', collateralRemainderOfCandy);

    // Line 107
    uint256 cllateralRemainderCapOfBob = Math.mulDivDown(debtInCollateralTokenOfBob, size.riskConfig().crLiquidation, PERCENT);
    uint256 cllateralRemainderCapOfCandy = Math.mulDivDown(debtInCollateralTokenOfBob, size.riskConfig().crLiquidation, PERCENT);
    console2.log('collateral remainder cap of Bob    => ', cllateralRemainderCapOfBob);
    console2.log('collateral remainder cap of Candy  => ', cllateralRemainderCapOfCandy);

    // collateralRemainder = Math.min(collateralRemainder, collateralRemainderCap);(Line 110)
    collateralRemainderOfBob = Math.min(collateralRemainderOfBob, cllateralRemainderCapOfBob);
    collateralRemainderOfCandy = Math.min(collateralRemainderOfCandy, cllateralRemainderCapOfCandy);
    console2.log('collateral remainder of Bob    => ', collateralRemainderOfBob);
    console2.log('collateral remainder of Candy  => ', collateralRemainderOfCandy);

    // protocolProfitCollateralToken = Math.mulDivDown(collateralRemainder, collateralProtocolPercent, PERCENT); (Line 112)
    uint256 protocolProfitCollateralTokenOfBob = Math.mulDivDown(collateralRemainderOfBob, collateralProtocolPercent, PERCENT);
    uint256 protocolProfitCollateralTokenOfCandy = Math.mulDivDown(collateralRemainderOfCandy, collateralProtocolPercent, PERCENT);
    console2.log('protocol profit collateral token of Bob    => ', protocolProfitCollateralTokenOfBob);
    console2.log('protocol profit collateral token of Candy  => ', protocolProfitCollateralTokenOfCandy);

    uint256 balanceOfProtocolForBobBefore = size.data().collateralToken.balanceOf(size.feeConfig().feeRecipient);
    _liquidate(liquidator, debtPositionIdOfBob, 0);
    uint256 balanceOfProtocolForBobAfter = size.data().collateralToken.balanceOf(size.feeConfig().feeRecipient);

    uint256 balanceOfProtocolForCandyBefore = size.data().collateralToken.balanceOf(size.feeConfig().feeRecipient);
    _liquidate(liquidator, debtPositionIdOfCandy, 0);
    uint256 balanceOfProtocolForCandyAfter = size.data().collateralToken.balanceOf(size.feeConfig().feeRecipient);

    // The actual profit matches the calculation above.
    assertEq(protocolProfitCollateralTokenOfBob, balanceOfProtocolForBobAfter - balanceOfProtocolForBobBefore);
    assertEq(protocolProfitCollateralTokenOfCandy, balanceOfProtocolForCandyAfter - balanceOfProtocolForCandyBefore);
}
```

## Recommendation

```solidity
function executeLiquidate(State storage state, LiquidateParams calldata params)
            external
            returns (uint256 liquidatorProfitCollateralToken)
        {
            if (assignedCollateral > debtInCollateralToken) {
                uint256 liquidatorReward = Math.min(
                    assignedCollateral - debtInCollateralToken,
                    Math.mulDivUp(debtPosition.futureValue, state.feeConfig.liquidationRewardPercent, PERCENT)
                );  
                liquidatorProfitCollateralToken = debtInCollateralToken + liquidatorReward;  

                uint256 collateralRemainder = assignedCollateral - liquidatorProfitCollateralToken; 

        -        uint256 cllateralRemainderCap =
                    Math.mulDivDown(debtInCollateralToken, state.riskConfig.crLiquidation, PERCENT);
        +        uint256 cllateralRemainderCap =
                    Math.mulDivDown(debtInCollateralToken, state.riskConfig.crLiquidation - PERCENT, PERCENT); 
            }
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect calculation of the collateral remainder cap that is applied when an overdue loan is liquidated. The contract is supposed to split the collateral that remains after the liquidator receives the debt amount plus a reward between the borrower and the protocol, but the cap that limits the protocol’s share is computed using the full liquidation collateral ratio (for example 130%) instead of the excess portion above the debt (30%). This root‑cause stems from a formula that multiplies the debt amount by the liquidation ratio directly, rather than by the difference between the liquidation ratio and 100 percent. When the cap is too large, the protocol can claim a larger slice of the remaining collateral, and borrowers with a higher collateral ratio lose more than those with a lower ratio even though both positions have the same debt size. An attacker can trigger liquidation on any overdue position that is not underwater; the contract will then allocate an inflated protocol fee, effectively stealing additional collateral from borrowers who over‑collateralised their loan. The impact is that users see less collateral returned than expected, with higher‑CR users experiencing a disproportionate loss, which undermines the economic incentive to provide ample collateral and may erode confidence in the protocol’s fairness. The condition for exploitation is that the loan is overdue, the borrower’s collateral ratio exceeds the liquidation threshold, and the liquidation function is called. Affected parties include borrowers whose collateral is partially confiscated, the protocol fee recipient that receives an unintended excess, and liquidators who may benefit from the mis‑allocation. The issue was discovered during a formal audit when test cases showed that two borrowers with identical debt but different collateral ratios received different protocol profit amounts, revealing that the cap calculation was using the full 130 percent instead of the 30 percent excess. The bug is subtle because the cap calculation appears syntactically correct and only diverges in edge cases where collateral ratios differ, making it easy to overlook without comparative testing. To remediate, the cap should be computed as debt × (crLiquidation − 100 percent) / 100 percent, or equivalently using the excess collateral ratio, ensuring that only the surplus above the debt is eligible for protocol fees. This adjustment restores the intended accounting logic where the protocol’s share is limited to the excess collateral, aligning user expectations with actual outcomes and preserving the incentive for higher collateralisation.
