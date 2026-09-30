---
id: 19604
severity: "Medium"
---

# There is no way to liquidate a position if it breaches `maxDebtPerCollateralToken` value creating bad debt.

## Description

Liquidations in the system are done via `LendingTerm._call()`, which will auction the loan’s collateral to repay outstanding debt. A loan can be called only if the term has been offboarded or if a loan missed a periodic `partialRepay`. To understand the issue, we must understand how the loan is created and how it can be called.

First, when a loan is created through a call to `_borrow()`, the contract checks if the `borrowAmount` is lesser than the `maxBorrow`:
```solidity
uint256 maxBorrow = (collateralAmount * params.maxDebtPerCollateralToken) / creditMultiplier;
require(
    borrowAmount <= maxBorrow,
    "LendingTerm: not enough collateral"
);
```
It calculates `maxBorrow` using `params.maxDebtPerCollateralToken`. For example, if `maxDebtPerCollateralToken` is 2000e18, then with 15e18 tokens of collateral, a user can borrow up to `30_000` of CREDIT tokens.

It’s also important to understand how liquidations work in the system. If we were to look at `_call()` function we could notice that it only allows liquidations in two specific cases:
```solidity
require(
    GuildToken(refs.guildToken).isDeprecatedGauge(address(this)) ||
        partialRepayDelayPassed(loanId),
    "LendingTerm: cannot call"
);
```
It will only allow to call a position if a term is depreciated or if the loan missed periodic partial repayment. This approach creates problems and opens up a griefing attack vector.

There are few ways it can go wrong. Let’s firstly discuss an issue that will arise even for a non-malicious user. In order for a user to not get liquidated, he must call `partialRepay()` before a specific deadline set in term’s parameters. If we look at the `_partialRepay()` function:
```solidity
require(
    debtToRepay >= (loanDebt * params.minPartialRepayPercent) / 1e18,
    "LendingTerm: repay below min"
);
```
We can see, that it enforces user to repay at least `params.minPartialRepayPercent`, which may not always be enough for a position to stay “healthy”. By “healthy” I mean a position that does not breach `maxDebtPerCollateralToken` value, which is a parameter of a LendingTerm.

Imagine a scenario:

  * Interest rate = 15%
  * `minPartialRepayPercent` = 10%
  * `maxDebtPerCollateralToken` = 2000

User borrows `30_000` CREDIT with 15 TOKENS of collateral. His `debtPerCollateral` value is `30_000 / 15 = 2000`, which is exactly equal to `maxDebtPerCollateralToken`. Now a year has passed, the `loanDebt` (debt + interest) is `34_500`, a user is obligated to repay at least `34_500 * 0.1 = 3450`. After partial repayment his `debtPerCollateral` value is `(34500 - 3450) / 15 = 2070`. While he breached the `maxDebtPerCollateralToken` value, his position is not callable, because he did not miss a periodic partial repayment.

Also it’s worth noting, that currently even if a user missed a periodic partial repayment, he can still make a call to `partialRepay()` if his position was not yet called. Because of this, it will be easier for such situation to occur, since the interest will be accruing and when a user finally calls `partialRepay()` he is still only obligated to repay at least `minPartialRepayPercent` for a position that went even deeper underwater.

Currently, due to a combination of multiple factors, bad debt can essentially occur and it will be impossible to liquidate such position without offboarding a term.

Now let’s talk about a potential malicious behaviour that is encouraged in the current implementation. Periodic partial repayments are not enforced for every term, they may or may not be enabled, so the only condition for a liquidation in this case is a depreceated term. This means that basically every position is essentially “unliquitable”, because `partialRepayDelayPassed()` will always return false in such case:
```solidity
function partialRepayDelayPassed(
    bytes32 loanId
) public view returns (bool) {
    // if no periodic partial repays are expected, always return false
    if (params.maxDelayBetweenPartialRepay == 0) return false;
```
A malicious user can abuse this by not repaying his loan or by not adding collateral to his loan when interest accrues above `maxDebtPerCollateralToken`. There will be no way to do anything with such positions, the only possible solution would be to offboard a full term. This will obviously damage the protocol, as offboarding a term means calling every position, which subsequently increases a chance of a loss occurring. Also by offboarding a term, lenders will miss out on interest, because every position is force-closed.

The current plan of the protocol was to have `partialRepay` of at least `interestRate` every year, so that positions do not grow into insolvent territory.

It’s hard and unreasonable to know every set of parameters that can lead to `debtPerCollateral` being greater than `maxDebtPerCollateralToken` even after `partialRepay`. After a discussion with the sponsor, it was said that ultimately the protocol team will not be the only one to deploy new terms, so it’s better to enforce a proper liquidation flow in the contract.

## Proof of Concept

```solidity
function testBreakMaxDebtPerCollateralToken() public {
    // prepare
    uint256 borrowAmount = 30_000e18;
    uint256 collateralAmount = 15e18;
    collateral.mint(address(this), collateralAmount);
    collateral.approve(address(term), collateralAmount);
    credit.approve(address(term), type(uint256).max);

    // borrow
    bytes32 loanId = term.borrow(borrowAmount, collateralAmount);
    vm.warp(block.timestamp + (term.YEAR() * 3));
    // 3 years have passed, and now position's debt is 39_000
    uint256 loanDebt = term.getLoanDebt(loanId);
    assertEq(loanDebt, 39_000e18);
    // A user is able to call partialRepays even if he missed partialRepays deadline
    term.partialRepay(
        loanId,
        (loanDebt * _MIN_PARTIAL_REPAY_PERCENT) / 1e18
    );
    // After repaying just minPartialRepayPercent, a debtPerCollateralToken of the position is 2080, which is greater than maxDebtPerCollateral
    uint256 newLoanDebt = term.getLoanDebt(loanId);
    assertEq((newLoanDebt / 15e18) * 1e18, 2080000000000000000000);
    assertGt((newLoanDebt / 15e18) * 1e18, _CREDIT_PER_COLLATERAL_TOKEN);

    // A position cannot be called
    vm.expectRevert("LendingTerm: cannot call");
    term.call(loanId);
}
```

Please add this function to LendingTerm.t.sol and run it with `forge test --match-test 'testBreakMaxDebtPerCollateralToken' -vv`.

In conclusion I want to say that parameters of a LendingTerm are only limited to a logical sort of degree, i.e:

  * Interest rate can be anything from 0 to 100%.
  * `maxDelayBetweenPartialRepay` can be anything from 0 to 1 year.
  * `minPartialRepayPercent` can be anything from 0 to 100%.

Because of this the situation is bound to occur. It’s better to enforce strict rules on the smart contract level.

## Recommendation

If periodic partial repays are turned on, the possible solution would be to enforce the `maxDebtPerCollateral` check in `_partialRepay`, that will enforce users to repay an amount that would make `debtPerCollateralToken` value lesser than `maxDebtPerCollateralToken` value.

Something like this would be sufficient enough:
```solidity
require(loan.debtPerCollateralToken <= param.maxDebtPerCollateralToken, "Position is not healthy.");
```
In the case of partial repays being turned on, it’s important to have this check in `_partialRepay()` rather than in `_call()`, because otherwise almost every position would immediately go underwater and be liquidatable as soon as it gets opened if a user borrowed up to the maximum amount. It’s fine to have `debtPerCollateralToken` greater than `maxDebtPerCollateralToken` until user makes a `partialRepay`.

In the case of periodic partial repays being turned off, the check must be in `_call()`, since there will be no partial repays. Check if `debtPerCollateralToken` value is lesser than `maxDebtPerCollateral` token, otherwise liquidate a position, but that would mean that users won’t be able to borrow up to `maxDebtPerCollateral`, since their position will immediately go underwater; it seems to be a matter of trade-offs. This the potential way to modify `_call()`:
```solidity
require(
    GuildToken(refs.guildToken).isDeprecatedGauge(address(this)) ||
        partialRepayDelayPassed(loanId) ||
        (params.maxDelayBetweenPartialRepay == 0 &&
            loan.debtPerCollateralToken > params.maxDebtPerCollateral),
    "LendingTerm: cannot call"
);
```
Confirming this, thanks for the high quality of the report!

On one hand, I think it might be considered a governance issue if the chosen term parameters allow loans to grow into unsafe territory, and that the situation is handled properly in the current implementation because GUILD holders can offboard the term if any loan of the term is unsafe. On the other hand, I don’t think it’s a large code change to allow loans to be called if they violate the “max debt check that is in `_borrow`” during their lifetime. It is an elegant addition to the codebase that we’ll probably do, so I think it’s worth including in the audit report.

@TrungOre - I would like to point out that this issue is about loans violating `maxDebtPerCollateral` check that is in `_borrow()` function during their lifetime. 

The current implementation of a LendingTerm offers 2 ways a system can work: partial repays may be enabled and may be disabled. In my submission, I clearly state two impacts of this issue to the system, one for the case when partial repays are expected and loans cannot be called despite violating aforementioned check and one for the case when partial repays are not expected and in such case loans also cannot be called, despite violating the check. The root cause of this is the lack of `health factor` check and not `maxDelayBetweenPartialRepay` being set to `0`.

Other issues grouped under this primary do not correctly identify the root cause, do not describe the same vulnerability and only talk about the specific case when `maxDelayBetweenPartialRepay = 0`, thus the recommended mitigations for such issues also do not address the problem properly. Given all of this context, I would like to ask you to reevaluate the judging on relevant duplicates under this primary.

@sl1 - Firstly, I want to refer to the sponsor’s statement and point out that your scenario is also a case of unsafe configs for a lending term. 

On one hand, I think it might be considered a governance issue if the chosen term parameters allow loans to grow into unsafe territory, and that the situation is handled properly in the current implementation because GUILD holders can offboard the term if any loan of the term is unsafe.

The configs in your scenario require a large interest rate and repayment duration, resulting in growing interest higher than `minPartialRepayPercent`. I believe the likelihood of this scenario doesn’t differ from the case when `maxDelayBetweenPartialRepay` == 0, as both cases represent unsafe and risky configs that need careful on-boarding and off-boarding from governance and users.

From the start, I had doubts about the severity of whether these issues should be considered as medium or QA, since everyone will be aware of the term’s configs before onboarding. However, I acknowledge that these represent potential risks, and the mitigation is both useful and necessary.

Secondly, there are only 2 cases that can cause a loan to breach `maxDebtPerCollateralToken`: a lending term with interest growing faster than the minimum repayment (your scenario) and a lending term with non-periodic payment loans (`maxDelayBetweenPartialRepay` == 0). Both of these unsafe cases lack a liquidation mechanism when the loan exceeds `maxDebtPerCollateralToken`. Therefore, I believe they share the same root cause and should be marked as duplicates.

_Note: For full discussion, see[here](https://github.com/code-423n4/2023-12-ethereumcreditguild-findings/issues/1057)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a liquidation dead‑end that occurs when a loan’s debt‑to‑collateral ratio exceeds the term’s maxDebtPerCollateralToken limit but the contract does not allow the position to be called for auction. The root cause is the absence of a health‑factor check after the initial borrow: while the _borrow function enforces debtPerCollateralToken ≤ maxDebtPerCollateralToken at loan creation, subsequent interest accrual and partial repayments are only constrained by a minimum repayment percentage (minPartialRepayPercent). The _call function, which triggers liquidation, permits execution only if the term is deprecated or if a periodic partial repayment deadline has been missed. When partial repayments are enabled, the deadline may never be considered missed because the function partialRepayDelayPassed returns false if maxDelayBetweenPartialRepay is zero, and even when a deadline is missed the contract still allows a partial repayment that may leave the loan still underwater. Consequently, a loan can drift into a state where debtPerCollateralToken > maxDebtPerCollateralToken while still satisfying the call pre‑condition, making it impossible to liquidate. This creates bad debt that cannot be recovered without off‑boarding the entire term, which forces a forced closure of all positions and results in loss of accrued interest for lenders. The issue manifests under any configuration where interest accrues faster than the required minimum repayment or where periodic partial repayments are disabled. Both honest users who simply miss a repayment deadline and malicious actors who deliberately avoid repaying can trigger the condition, leading to funds disappearing from the borrower’s perspective (the collateral remains locked) and lenders receiving less than expected returns. The problem was discovered during a manual audit that examined the interaction between _borrow, _partialRepay and _call, and it is subtle because the contract does appear to enforce a max debt limit at loan creation, giving a false sense of safety. Detecting the bug requires tracing the state changes over time and understanding that the liquidation guard does not re‑evaluate the health factor after interest accrues. To remediate, a health‑factor check (debtPerCollateralToken ≤ maxDebtPerCollateralToken) should be added either in the _partialRepay function when partial repayments are enabled, or in the _call function when they are disabled, ensuring that any position that becomes under‑collateralised can be liquidated promptly. This change restores the intended economic guarantees of the lending term and prevents the creation of unliquidatable bad debt.
