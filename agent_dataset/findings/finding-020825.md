---
id: 20825
severity: "High"
---

# Incorrect bad debt accounting can lead to a state where the `claimFeesBeneficial` function is permanently bricked and no new incentives can be distributed, potentially locking pending and future protocol fees in the `FeeManager` contract

## Description

```solidity
if (totalBadDebtETH == 0) { // @audit: incentives only distributed if there is no global bad debt

    tokenAmount = _distributeIncentives( // @audit: distributes incentives for `incentive owners` via `gatheredIncentiveToken` mapping
        tokenAmount,
        _poolToken,
        underlyingTokenAddress
    );
}
```
```solidity
function claimIncentives(
    address _feeToken
)
    public
{
    uint256 amount = gatheredIncentiveToken[msg.sender][_feeToken]; // @audit: mapping incremented in _distributeIncentives function

    if (amount == 0) {
        revert NoIncentive();
    }
}
```
```solidity
function claimFeesBeneficial(
    address _feeToken,
    uint256 _amount
)
    external
{
    address caller = msg.sender;

    if (totalBadDebtETH > 0) { // @audit: can't claim fees when there is bad debt
        revert ExistingBadDebt();
    }
}
```
Below I will explain how the bad debt accounting logic used during partial liquidations can result in a state where `totalBadDebtETH` is permanently greater than `0`. When this occurs, `beneficials` will no longer be able to claim fees via the `FeeManager::claimFeesBeneficial` function and new incentives will no longer be distributed when fees are permissionlessly collected via the `FeeManager::claimWiseFees` function.

When a position is partially liquidated, the `WiseSecurity::checkBadDebtLiquidation` function is executed to check if the position has created bad debt, i.e. if the position’s overall borrow value is greater than the overall (unweighted) collateral value. If the post liquidation state of the position created bad debt, then the bad debt is recorded in a global and position-specific state:
```solidity
function checkBadDebtLiquidation(
    uint256 _nftId
)
    external
    onlyWiseLending
{
    uint256 bareCollateral = overallETHCollateralsBare(
        _nftId
    );

    uint256 totalBorrow = overallETHBorrowBare(
        _nftId
    );

    if (totalBorrow < bareCollateral) { // @audit: LTV < 100%
        return;
    }

    unchecked {
        uint256 diff = totalBorrow
            - bareCollateral;

        FEE_MANAGER.increaseTotalBadDebtLiquidation( // @audit: global state, totalBadDebtETH += diff
            diff
        );

        FEE_MANAGER.setBadDebtUserLiquidation( // @audit: position state, badDebtPosition[_nftId] = diff
            _nftId,
            diff
        );
    }
}
```
```solidity
function _setBadDebtPosition(
    uint256 _nftId,
    uint256 _amount
)
    internal
{
    badDebtPosition[_nftId] = _amount; // @audit: position bad debt set
}

/**
 * @dev Internal increase function for global bad debt amount.
 */
function _increaseTotalBadDebt(
    uint256 _amount
)
    internal
{
    totalBadDebtETH += _amount; // @audit: total bad debt incremented
}
```
As we can see above, the method by which the global and position’s state is updated is not consistent (total debt increases, but position’s debt is set to recent debt). Since liquidations can be partial, a position with bad debt can undergo multiple partial liquidations and each time the `totalBadDebtETH` will be incremented. However, the `badDebtPosition` for the position will only be updated with the most recent bad debt that was recorded during the last partial liquidation. Note that due to the condition on line 419 of `WiseSecurity::checkBadDebtLiquidation`, the `badDebtPosition` will be reset to `0` when `totalBorrow == bareCollateral` (`LTV == 100%`). However, in this case, any previously recorded bad debt for the position will _not_ be deducted from the `totalBadDebtETH`. Lets consider two examples:

**Scenario 1**: Due to a market crash, a position’s LTV goes above 100%. The position gets partially liquidated, incrementing `totalBadDebtETH` by `x` (bad debt from 1st liquidation) and setting `badDebtPosition[_nftId]` to `x`. The position gets partially liquidated again, this time incrementing `totalBadDebtETH` by `y` (bad debt from 2nd liquidation) and setting `badDebtPosition[_nftId]` to `y`. The resulting state:

    totalBadDebtETH == x + y
    badDebtPosition[_nftId] == y

**Scenario 2**: Due to a market crash, a position’s LTV goes above 100%. The position gets partially liquidated, incrementing `totalBadDebtETH` by `x` and setting `badDebtPosition[_nftId]` to `x`. The position gets partially liquidated again, but this time the `totalBorrow` is equal to `bareCollateral` (`LTV == 100%`) and thus no bad debt is created. Due to the condition on line 419, `totalBadDebtETH` will be incremented by `0`, but `badDebtPosition[_nftId]` will be reset to `0`. The resulting state:

    totalBadDebtETH == x
    badDebtPosition[_nftId] == 0

Note: Scenario 1 is more likely to occur since Scenario 2 requires the additional partial liquidation to result in an LTV of exactly 100% for the position.

As we can see, partial liquidations can lead to `totalBadDebtETH` being artificially inflated with respect to the actual bad debt created by a position.

When bad debt is created, it is able to be paid back via the [`FeeManager::paybackBadDebtForToken`](https://github.com/code-423n4/2024-02-wise-lending/blob/main/contracts/FeeManager/FeeManager.sol#L730-L744) or [`FeeManager::paybackBadDebtNoReward`](https://github.com/code-423n4/2024-02-wise-lending/blob/main/contracts/FeeManager/FeeManager.sol#L816-L826) functions. However, the maximum amount of bad debt that can be deducted during these calls is capped at the bad debt recorded for the position specified (`badDebtPosition[_nftId]`). Therefore, the excess “fake” bad debt can not be deducted from `totalBadDebtETH`, resulting in `totalBadDebtETH` being permanently greater than `0`.

Below is the logic that deducts the bad debt created by a position when it is paid off via one of the payback functions mentioned above:
```solidity
unchecked {
    uint256 newBadDebt = currentBorrowETH
        - currentCollateralBareETH;

    _setBadDebtPosition( // @audit: badDebtPosition[_nftId] = newBadDebt
        _nftId,
        newBadDebt
    );

    newBadDebt > currentBadDebt // @audit: totalBadDebtETH updated with respect to change in badDebtPosition
        ? _increaseTotalBadDebt(newBadDebt - currentBadDebt)
        : _decreaseTotalBadDebt(currentBadDebt - newBadDebt);
}
```
The above code is invoked in the [`FeeManagerHelper::updatePositionCurrentBadDebt`](https://github.com/code-423n4/2024-02-wise-lending/blob/main/contracts/FeeManager/FeeManagerHelper.sol#L270-L285) function, which is in turn invoked during both of the payback functions previously mentioned. You will notice that the above code properly takes into account the change in the bad debt of the position in question. I.e. if the `badDebtPosition[_nftId]` decreased (after being paid back), then the `totalBadDebtETH` will decrease as well. Therefore, the `totalBadDebtETH` can only be deducted by at most the current bad debt of a position. Returning to the previous example in Scenario 1, this means that `totalBadDebtETH` would remain equal to `x`, since only `y` amount of bad debt can be paid back.

## Proof of Concept

Place the following test in the `contracts/` directory and run with `forge test --match-path contracts/BadDebtTest.t.sol`:
```solidity
// SPDX-License-Identifier: -- WISE --

pragma solidity =0.8.24;

import "./WiseLendingBaseDeployment.t.sol";

contract BadDebtTest is BaseDeploymentTest {
    address borrower = address(0x01010101);
    address lender = address(0x02020202);

    uint256 depositAmountETH = 10e18; // 10 ether
    uint256 depositAmountToken = 10; // 10 ether
    uint256 borrowAmount = 5e18; // 5 ether

    uint256 nftIdLiquidator; // nftId of lender
    uint256 nftIdLiquidatee; // nftId of borrower

    uint256 debtShares;

    function _setupIndividualTest() internal override {
        _deployNewWiseLending(false);

        // set token value for simple calculations
        MOCK_CHAINLINK_2.setValue(1 ether); // 1 token == 1 ETH
        assertEq(MOCK_CHAINLINK_2.latestAnswer(), MOCK_CHAINLINK_ETH_ETH.latestAnswer());
        vm.stopPrank();
        
        // fund lender and borrower
        vm.deal(lender, depositAmountETH);
        deal(address(MOCK_WETH), lender, depositAmountETH);
        deal(address(MOCK_ERC20_2), borrower, depositAmountToken * 2);
    }

    function testScenario1() public {
        // --- scenario is set up --- //
        _setUpScenario();

        // --- shortfall event/crash creates bad debt, position partially liquidated logging bad debt --- //
        _marketCrashCreatesBadDebt();

        // --- borrower gets partially liquidated again --- //
        vm.prank(lender);

        LENDING_INSTANCE.liquidatePartiallyFromTokens(
            nftIdLiquidatee,
            nftIdLiquidator, 
            address(MOCK_WETH),
            address(MOCK_ERC20_2),
            debtShares * 2e16 / 1e18
        );

        // --- global bad det increases again, but user bad debt is set to current bad debt created --- // 
        uint256 newTotalBadDebt = FEE_MANAGER_INSTANCE.totalBadDebtETH();
        uint256 newUserBadDebt = FEE_MANAGER_INSTANCE.badDebtPosition(nftIdLiquidatee);
        
        assertGt(newUserBadDebt, 0); // userBadDebt reset to new bad debt, newUserBadDebt == current_bad_debt_created
        assertGt(newTotalBadDebt, newUserBadDebt); // global bad debt incremented again
        // newTotalBadDebt = old_global_bad_debt + current_bad_debt_created
        
        // --- user bad debt is paid off, but global bad is only partially paid off (remainder is fake debt) --- // 
        _tryToPayBackGlobalDebt();

        // --- protocol fees can no longer be claimed since totalBadDebtETH will remain > 0 --- // 
        vm.expectRevert(bytes4(keccak256("ExistingBadDebt()")));
        FEE_MANAGER_INSTANCE.claimFeesBeneficial(address(0), 0);
    }

    function testScenario2() public {
        // --- scenario is set up --- // 
        _setUpScenario();

        // --- shortfall event/crash creates bad debt, position partially liquidated logging bad debt --- //
        _marketCrashCreatesBadDebt();
        
        // --- Position manipulated so second partial liquidation results in totalBorrow == bareCollateral --- //
        // borrower adds collateral
        vm.prank(borrower);

        LENDING_INSTANCE.solelyDeposit(
            nftIdLiquidatee, 
            address(MOCK_ERC20_2), 
            6
        );

        // borrower gets partially liquidated again
        vm.prank(lender);

        LENDING_INSTANCE.liquidatePartiallyFromTokens(
            nftIdLiquidatee,
            nftIdLiquidator, 
            address(MOCK_WETH),
            address(MOCK_ERC20_2),
            debtShares * 2e16 / 1e18
        );
        
        uint256 collateral = SECURITY_INSTANCE.overallETHCollateralsBare(nftIdLiquidatee);
        uint256 debt = SECURITY_INSTANCE.overallETHBorrowBare(nftIdLiquidatee);
        assertEq(collateral, debt); // LTV == 100% exactly

        // --- global bad debt is unchanged, while user bad debt is reset to 0 --- // 
        uint256 newTotalBadDebt = FEE_MANAGER_INSTANCE.totalBadDebtETH();
        uint256 newUserBadDebt = FEE_MANAGER_INSTANCE.badDebtPosition(nftIdLiquidatee);

        assertEq(newUserBadDebt, 0); // user bad debt reset to 0
        assertGt(newTotalBadDebt, 0); // global bad debt stays the same (fake debt)

        // --- attempts to pay back fake global debt result in a noop, totalBadDebtETH still > 0 --- // 
        uint256 paybackShares = _tryToPayBackGlobalDebt();
        
        assertEq(LENDING_INSTANCE.userBorrowShares(nftIdLiquidatee, address(MOCK_WETH)), paybackShares); // no shares were paid back

        // --- protocol fees can no longer be claimed since totalBadDebtETH will remain > 0 --- //
        vm.expectRevert(bytes4(keccak256("ExistingBadDebt()")));
        FEE_MANAGER_INSTANCE.claimFeesBeneficial(address(0), 0);
    }

    function _setUpScenario() internal {
        // lender supplies ETH
        vm.startPrank(lender);

        nftIdLiquidator = POSITION_NFTS_INSTANCE.mintPosition();

        LENDING_INSTANCE.depositExactAmountETH{value: depositAmountETH}(nftIdLiquidator);

        vm.stopPrank();

        // borrower supplies collateral token and borrows ETH
        vm.startPrank(borrower);

        MOCK_ERC20_2.approve(address(LENDING_INSTANCE), depositAmountToken * 2);

        nftIdLiquidatee = POSITION_NFTS_INSTANCE.mintPosition();
        
        LENDING_INSTANCE.solelyDeposit( // supply collateral
            nftIdLiquidatee, 
            address(MOCK_ERC20_2), 
            depositAmountToken
        );

        debtShares = LENDING_INSTANCE.borrowExactAmountETH(nftIdLiquidatee, borrowAmount); // borrow ETH

        vm.stopPrank();
    }

    function _marketCrashCreatesBadDebt() internal {
        // shortfall event/crash occurs
        vm.prank(MOCK_DEPLOYER);

        MOCK_CHAINLINK_2.setValue(0.3 ether);

        // borrower gets partially liquidated
        vm.startPrank(lender);

        MOCK_WETH.approve(address(LENDING_INSTANCE), depositAmountETH);

        LENDING_INSTANCE.liquidatePartiallyFromTokens(
            nftIdLiquidatee,
            nftIdLiquidator, 
            address(MOCK_WETH),
            address(MOCK_ERC20_2),
            debtShares * 2e16 / 1e18 + 1 
        );

        vm.stopPrank();

        // global and user bad debt is increased
        uint256 totalBadDebt = FEE_MANAGER_INSTANCE.totalBadDebtETH();
        uint256 userBadDebt = FEE_MANAGER_INSTANCE.badDebtPosition(nftIdLiquidatee);

        assertGt(totalBadDebt, 0); 
        assertGt(userBadDebt, 0);
        assertEq(totalBadDebt, userBadDebt); // user bad debt and global bad debt are the same
    }

    function _tryToPayBackGlobalDebt() internal returns (uint256 paybackShares) {
        // lender attempts to pay back global debt
        paybackShares = LENDING_INSTANCE.userBorrowShares(nftIdLiquidatee, address(MOCK_WETH));
        uint256 paybackAmount = LENDING_INSTANCE.paybackAmount(address(MOCK_WETH), paybackShares);

        vm.startPrank(lender);

        MOCK_WETH.approve(address(FEE_MANAGER_INSTANCE), paybackAmount);
        
        FEE_MANAGER_INSTANCE.paybackBadDebtNoReward(
            nftIdLiquidatee, 
            address(MOCK_WETH), 
            paybackShares
        );

        vm.stopPrank();

        // global bad debt and user bad debt updated
        uint256 finalTotalBadDebt = FEE_MANAGER_INSTANCE.totalBadDebtETH();
        uint256 finalUserBadDebt = FEE_MANAGER_INSTANCE.badDebtPosition(nftIdLiquidatee);

        assertEq(finalUserBadDebt, 0); // user has no more bad debt, all paid off
        assertGt(finalTotalBadDebt, 0); // protocol still thinks there is bad debt
    }
}
```

## Recommendation

I would recommend updating `totalBadDebtETH` with the `difference` of the previous and new bad debt of a position in the `WiseSecurity::checkBadDebtLiquidation` function, similar to how it is done in the `FeeManagerHelper::_updateUserBadDebt` internal function.

Example implementation:
```diff
diff --git a/./WiseSecurity/WiseSecurity.sol b/./WiseSecurity/WiseSecurity.sol
index d2cfb24..75a34e8 100644
--- a/./WiseSecurity/WiseSecurity.sol
+++ b/./WiseSecurity/WiseSecurity.sol
@@ -424,14 +424,22 @@ contract WiseSecurity is WiseSecurityHelper, ApprovalHelper {
                 uint256 diff = totalBorrow
                     - bareCollateral;

-            FEE_MANAGER.increaseTotalBadDebtLiquidation(
-                diff
-            );
+            uint256 currentBadDebt = FEE_MANAGER.badDebtPosition(_nftId);

                 FEE_MANAGER.setBadDebtUserLiquidation(
                     _nftId,
                     diff
                 );
+
+            if (diff > currentBadDebt) {
+                FEE_MANAGER.increaseTotalBadDebtLiquidation(
+                    diff - currentBadDebt
+                );
+            } else {
+                FEE_MANAGER.decreaseTotalBadDebtLiquidation(
+                    currentBadDebt - diff
+                );
+            }
             }
         }
```
This doesn’t lead to loss of user funds though. Hence, it should be downgraded since one could just migrate and redeploy after discovering that. Otherwise good find.

Would agree with that! This is a good insight, but users’ funds are never at risk. This is related to the `feeManager` and the fees taken from the protocol. Therefore, a Medium issue.

### Summary of the issue

When a market accrues bad debt, which can be inflated due to an accounting error, fees and incentives will no longer be distributed. _Note: The discussion had quite a bit of back and forth, for this reason the whole conversation is pasted below:_

### Discussion

**Alex the Entreprenerd (Appellate Court lead judge) commented:** This seems to be tied to a specific interpretation of this discussion we’ve had around loss of yield as high.

**hickuphh3 (judge 2) commented:** Fees would be considered as matured yield? Given that it extends beyond the protocol to beneficials and incentive owners, I’m leaning towards a high more than a medium.

**Alex the Entreprenerd (Appellate Court lead judge) commented:** Yes it would be considered matured. I don’t have an opinion on this report yet and will follow up later today with my notes.

Not fully made up my mind but here’s a couple of points:

For Medium: Loss of Yield -> There is no loss of principal so Med seems fine.

For High: The contract is not losing yield in some case, the contract is losing 100% of all yield. The contract is no longer serving it’s purpose.

External Conditions: Bad debt must be formed. Bad debt handling is part of the system design, so assuming this can happen is fair, and starting from a scenario in which this can happen is also fair.

That said, in reality, this may never happen.

My main point for downgrading is that while the contract is losing all of the yield, nothing beside that is impacted, not fully sure on this one.

**LSDan (judge 3) commented:** I’m aligned with high on this one. Even though the conditions that lead to it are rare and there are arguably external conditions in some scenarios, there is a direct loss of funds and the functional loss of a contract’s purpose. Once this situation occurs, there is no clean way back from it.

**Alex the Entreprenerd (Appellate Court lead judge) commented:** I think this is the issue where we will have some contention. I think the Sponsor interpretation is important to keep in mind as it’s pretty rational. I would like to think about it a bit more.

**Alex the Entreprenerd (Appellate Court lead judge) commented:** I’m leaning towards Med on this report, I think the Sponsors POV is valid.

There is an accounting error, it would not cause permanent loss of funds. It would be mitigated by deprecating the market and creating a new one.

My main argument is that if this was live, this would trigger a re-deploy but it would not trigger any white hat rescue operation, as funds would be safe.

**hickuphh3 (judge 2) commented**: [#74](https://github.com/code-423n4/2024-02-wise-lending-findings/issues/74): When we stick to the c4a rules to which we agreed, all the loss of fees are no user funds and therefore, should be treated differently.

The core argument for Medium severity is that fees are a secondary concern.

This goes against the supreme court decision where fees shouldn’t be treated as 2nd class citizens [here](https://docs.code4rena.com/awarding/judging-criteria/severity-categorization#loss-of-fees-as-low).

Loss of fees should be regarded as an impact similar to any other loss of capital. Loss of real amounts depends on specific conditions and likelihood considerations.

Likelihood: Requirement of bad debt formation. Once there is, funds (fees) are permanently bricked.

There is an accounting error, it would not cause permanent loss of funds; it would be mitigated by deprecating the market and creating a new one.

The funds you are referring to are user funds? Separately, I don’t see how it would mitigate the bricking once it happens.

**Alex the Entreprenerd (Appellate Court lead judge) commented:** I don’t think that the ruling means that loss of fees should be treated as high at all times.

The main argument is that the broken accounting doesn’t create a state that is not recoverable:

  * Some fees are lost.
  * User deprecates market (raises interests or pauses).
  * Deploys new Market.
  * System resumes functioning as intended.


My main argument is that this would not cause a War Room, it would cause a deprecation that the system can handle.

**hickuphh3 (judge 2) commented:** In what cases/scenarios would loss of fees be high then? Most, if not all, won’t have a war room for protocol fees.

The reason I would consider to justify downgrading is the low likelihood of the external requirement of bad debt formation `+` `>=` 2 partial liquidations.

I would dissent and argue for high severity.

  * Permanent loss of unclaimed fees.
  * Blast radius: affects not just the protocol, but incentive owners and beneficiaries.


Had the fees gone only to the protocol, I’d lean a bit more towards Medium.

Is `WiseLending` immutable in a `poolToken` instance?

What contracts would have to be re-deployed?

**Alex the Entreprenerd (Appellate Court lead judge) commented:** Liquidation premium being denied could be a valid High loss of yield, loss of gas for refunds when the system entire goal is that (e.g. keepers, voting on Nouns).

### Alex the Entreprenerd’s (Appellate Court lead judge) Input

The finding shows how in the specific case of liquidations with bad debt, a market will stop accounting for fees.

2 aggravating circumstances seem to be:

  * Inability to pause and replace each market.
  * The Math for bad debt is also wrong, leading to the inability to fix the bug.


This would still cause a loss of fees for a certain period of time, as the admin would eventually be able to set the market fees to either a state that would cause users to stop using it or `0` as a means to stop the loss.

I think that the accounting mistake is notable, and I understand the reasoning for raising severity.

That said, because we have to judge by impact of the finding, I believe Medium Severity to be most appropriate.

### hickuphh3’s (judge 2) Input

I maintain my stance for High severity for the reasons I stated above:

  * Permanent loss of unclaimed fees.
  * Impact on protocol ecosystem: beneficiaries and incentive owners.


### LSDan’s (judge 3) Input

I’m still of the opinion that High is most appropriate here. The impact is significant enough that raising the severity beyond medium makes sense.

### Deliberation

The severity is kept at High Severity, with a non-unanimous verdict.

### Additional Context by the Lead Judge

I recommend monitoring how this decision influences future decisions on severities, especially when it comes to a percentage loss of yield, an attacker having the button to cause a loss of yield, against this instance which is the permanent inability for the contract to record a gain of yield.

Mitigated [here](https://github.com/wise-foundation/lending-audit/commit/ac68b5a93976969d582301fee9f873ecec606df9).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inconsistency in the way the protocol records bad debt during partial liquidations. When a position becomes under‑collateralised, the global variable totalBadDebtETH is increased by the amount of newly created bad debt, while the per‑position mapping badDebtPosition is overwritten with only the most recent shortfall. Because liquidations can be partial, a position may incur bad debt several times; each liquidation adds to totalBadDebtETH but the mapping keeps only the last value, and it can even be reset to zero when the loan‑to‑value reaches exactly 100 %. The payback functions that reduce totalBadDebtETH are limited to the amount stored in badDebtPosition, so any excess “fake” bad debt that remains in the global counter can never be cleared. As a result, totalBadDebtETH stays greater than zero permanently. The contract contains a guard in claimFeesBeneficial that reverts with ExistingBadDebt whenever totalBadDebtETH is non‑zero, and the incentive distribution logic only runs when totalBadDebtETH equals zero. Consequently, once the accounting error occurs, beneficiaries and incentive owners are unable to claim protocol fees or rewards; calls to claimFeesBeneficial revert, and claimIncentives returns NoIncentive, leaving users with zero balances despite fees having been accrued. The issue was discovered during a formal audit and reproduced with a Forge test that simulates a market crash, partial liquidations, and subsequent fee claims. It is hard to notice because the global bad‑debt counter appears as a normal accounting figure and no user principal is lost; the symptom is a silent loss of yield and locked incentives. The bug affects the entire protocol, not just the liquidated position, because the global flag blocks fee distribution for all beneficiaries. The root cause is the failure to adjust totalBadDebtETH by the difference between the new and previous per‑position bad debt during liquidation, unlike the correct logic used in the fee‑manager helper when bad debt is repaid. A proper fix is to compute the delta between the newly calculated shortfall and the previously recorded badDebtPosition and apply that delta to totalBadDebtETH (increasing or decreasing as needed), ensuring that when a position’s bad debt is cleared or reduced, the global counter is updated accordingly. This restores the ability of the protocol to claim fees and distribute incentives once the bad‑debt state is accurate.
