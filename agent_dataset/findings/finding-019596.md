---
id: 19596
severity: "High"
---

# The creation of bad debt

## Description

The creation of bad debt results in the `mark down` of `Credit`, i.e. `Credit` experiences inflation. This is done so that the protocol can adjust to the bad debt that was produced. It follows that when `Credit` is marked down all active loans can be considered `marked up`; meaning, the borrowers will be expected to repay with more `Credit`, since `Credit` is now worthless. We can observe how this is done by examining the `LendingTerm::getLoanDebt` function:

[LendingTerm::getLoanDebt#L216-L230](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/LendingTerm.sol#L216-L230)

```solidity
// compute interest owed
uint256 borrowAmount = loan.borrowAmount;
uint256 interest = (borrowAmount *
    params.interestRate *
    (block.timestamp - borrowTime)) /
    YEAR /
    1e18;
uint256 loanDebt = borrowAmount + interest;
uint256 _openingFee = params.openingFee;
if (_openingFee != 0) {
    loanDebt += (borrowAmount * _openingFee) / 1e18;
}
uint256 creditMultiplier = ProfitManager(refs.profitManager)
    .creditMultiplier();
loanDebt = (loanDebt * loan.borrowCreditMultiplier) / creditMultiplier;
```

As we can see above, the debt of a borrower (principle + interests) is adjusted by the `creditMultiplier`. This `creditMultiplier` starts at `1e18` and gets `marked down` when bad debt is produced in the system. The `loan.borrowCreditMultiplier` is the `creditMultiplier` value at the time that the user took out the loan. Therefore, this function calculates the adjusted debt of a borrower with respect to the amount of bad debt that was produced (inflation of `Credit`) since the borrower took out the loan. This function is called every time a borrower makes a payment for their loan, ensuring that the appropriate debt is always considered. However, this function is only called once during the entire auction process:

[LendingTerm::_call#L664-L668](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/LendingTerm.sol#L664-L668)

```solidity
// update loan in state
uint256 loanDebt = getLoanDebt(loanId);
loans[loanId].callTime = block.timestamp;
loans[loanId].callDebt = loanDebt;
loans[loanId].caller = caller;
```

The above code is taken from the `_call` function, which is the starting point for an auction. When a loan misses a _required_ `partialPayment` or the term is offboarded, this function can be permissionlessly called. As we can see, the debt of the loan is read from the `getLoanDebt` function and then stored in the `loan` struct in the `callDebt` field. This means that the `callDebt` represents a snapshot of the debt at `block.timestamp`. Therefore, the `callDebt` is the loan debt with respect to the `creditMultiplier` valued at the time that the loan was called. What if the `creditMultiplier` gets updated after the auction process begins? This would result in the `callDebt` of the loan being less than what the actual debt of the loan should be (`Credit` is worth less, but the collateral is worth the same). We can understand the true magnitude of this discrepancy by observing the `LendingTerm::onBid` function:

[LendingTerm::onBid#L750-L768](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/LendingTerm.sol#L750-L768)

```solidity
// compute pnl
uint256 creditMultiplier = ProfitManager(refs.profitManager)
    .creditMultiplier();
uint256 borrowAmount = loans[loanId].borrowAmount;
uint256 principal = (borrowAmount *
    loans[loanId].borrowCreditMultiplier) / creditMultiplier;
int256 pnl;
uint256 interest;
if (creditFromBidder >= principal) {
    interest = creditFromBidder - principal;
    pnl = int256(interest);
} else {
    pnl = int256(creditFromBidder) - int256(principal);
    principal = creditFromBidder;
    require(
        collateralToBorrower == 0,
        "LendingTerm: invalid collateral movement"
    );
}
```

As we can see above, the `principle` of the loan is calculated with respect to the current `creditMultiplier`. The `creditFromBidder` is the `callDebt` when the auction is in its first phase:

[AuctionHouse::getBidDetail#L133-L136](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/AuctionHouse.sol#L133-L136)

```solidity
// first phase of the auction, where more and more collateral is offered
if (block.timestamp < _startTime + midPoint) {
    // ask for the full debt
    creditAsked = auctions[loanId].callDebt;
}
```

This is where the issue lies. Remember, the `callDebt` represents a snapshot of the loan debt at the time which the loan was called. The `callDebt` does not consider a potential updated `creditMultiplier`. Therefore, if a `mark down` is generated that results in `principle > creditFromBidder`, then execution of the `onBid` function would continue on line 762. This will result in a negative `pnl` being calculated, which ultimately means that this gauge will experience a loss. However, if the `collateralToBorrower` is _not_ `0`, the function will revert. Therefore, when the `principle` is greater than the `callDebt`, due to the `mark down` of `Credit`, the auction can only receive a bid if the `collateralToBorrower` is `0`. Let us observe the `AuctionHouse::bid` and `AuctionHouse::getBidDetail` functions in order to understand what scenario would result in `collateralToBorrower == 0`:

[AuctionHouse::bid#L169-L186](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/AuctionHouse.sol#L169-L186)

```solidity
(uint256 collateralReceived, uint256 creditAsked) = getBidDetail(
    loanId
);
require(creditAsked != 0, "AuctionHouse: cannot bid 0");
...
LendingTerm(_lendingTerm).onBid(
    loanId,
    msg.sender,
    auctions[loanId].collateralAmount - collateralReceived, // collateralToBorrower
    collateralReceived, // collateralToBidder
    creditAsked // creditFromBidder
);
```

As seen above, the `getBidDetail` function is invoked to retrieve the necessary `collateralReceived` and `creditAsked` values. The `onBid` function is then invoked and the `collateralToBorrower` is equal to the `collateralAmount - collateralReceived`. The `collateralAmount` is the full collateral of the loan. Therefore, if the `collateralReceived == collateralAmount`, we will have satisfied the following condition: `collateralToBorrower == 0`. This is exactly what occurs during the second phase of an auction:

[AuctionHouse::getBidDetail#L143-L146](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/AuctionHouse.sol#L143-L146)

```solidity
// second phase of the auction, where less and less CREDIT is asked
else if (block.timestamp < _startTime + auctionDuration) {
    // receive the full collateral
    collateralReceived = auctions[loanId].collateralAmount;
}
```

Therefore, given the situation where a loan is placed in auction and then a large enough `mark down` of `Credit` occurs, such that `principle > creditFromBidder`, only bids occurring during the second phase of the auction will be allowed. In addition, given that `principle > creditFromBidder`, bad debt will also be produced in this auction.

Let’s briefly discuss what scenarios would result in `principle > callDebt`. Reminder: The `callDebt` represents the maximum value that `creditFromBidder` can be. The `callDebt` is a snapshot of the full debt of a borrower (principle + interests). Therefore, if the `mark down` results in a percent decrease of `Credit` greater than the interest of the borrower’s loan, then the adjusted `principle` will be greater than the `callDebt`. Consider the following situation:

A term has an interest rate of 4%. The term has multiple loans opened and the term is being off-boarded after half a year. Let’s assume no loans have been paid off during this time. Therefore, the interest for all loans is ~2%. Suppose a loan undergoes auction before other loans are called and this loan results in the creation of bad debt (worst case scenario), which results in a `mark down` > 2%. All other loans that are in auction during this `mark down` will be forced to create bad debt since the adjusted `principle` for all loans in auction will be greater than the loans’ `callDebt`.

## Proof of Concept

The following test demonstrates the scenario described above in which a `mark down` of `Credit` results in other loans in auction being forced to create additional bad debt.

Place the test inside of the `test/unit/loan/` directory:

```solidity
// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity 0.8.13;

import {Clones} from "@openzeppelin/contracts/proxy/Clones.sol";

import {Test} from "@forge-std/Test.sol";
import {Core} from "@src/core/Core.sol";
import {CoreRoles} from "@src/core/CoreRoles.sol";
import {MockERC20} from "@test/mock/MockERC20.sol";
import {SimplePSM} from "@src/loan/SimplePSM.sol";
import {GuildToken} from "@src/tokens/GuildToken.sol";
import {CreditToken} from "@src/tokens/CreditToken.sol";
import {LendingTerm} from "@src/loan/LendingTerm.sol";
import {AuctionHouse} from "@src/loan/AuctionHouse.sol";
import {ProfitManager} from "@src/governance/ProfitManager.sol";
import {RateLimitedMinter} from "@src/rate-limits/RateLimitedMinter.sol";

contract BadDebtCreatesBadDebt is Test {
    address private governor = address(1);
    address private guardian = address(2);
    address staker = address(0x01010101);
    address borrower = address(0x02020202);
    address lender = address(0x03030303);
    Core private core;
    ProfitManager private profitManager;
    CreditToken credit;
    GuildToken guild;
    MockERC20 collateral;
    MockERC20 pegToken;
    SimplePSM private psm;
    RateLimitedMinter rlcm;
    AuctionHouse auctionHouse;
    LendingTerm term;

    // LendingTerm params (same as deployment script)
    uint256 constant _CREDIT_PER_COLLATERAL_TOKEN = 1e18; // 1:1
    uint256 constant _INTEREST_RATE = 0.04e18; // 4% APR
    uint256 constant _MAX_DELAY_BETWEEN_PARTIAL_REPAY = 0; 
    uint256 constant _MIN_PARTIAL_REPAY_PERCENT = 0; 
    uint256 constant _HARDCAP = 2_000_000e18; // 2 million

    uint256 public issuance = 0;

    function setUp() public {
        vm.warp(1679067867);
        vm.roll(16848497);
        core = new Core();

        profitManager = new ProfitManager(address(core));
        collateral = new MockERC20();
        pegToken = new MockERC20(); // 18 decimals for easy calculations (deployment script uses USDC which has 6 decimals)
        credit = new CreditToken(address(core), "name", "symbol");
        guild = new GuildToken(
            address(core),
            address(profitManager)
        );
        rlcm = new RateLimitedMinter(
            address(core) /*_core*/,
            address(credit) /*_token*/,
            CoreRoles.RATE_LIMITED_CREDIT_MINTER /*_role*/,
            0 /*_maxRateLimitPerSecond*/,
            0 /*_rateLimitPerSecond*/,
            uint128(_HARDCAP) /*_bufferCap*/
        );
        auctionHouse = new AuctionHouse(address(core), 650, 1800);
        term = LendingTerm(Clones.clone(address(new LendingTerm())));
        term.initialize(
            address(core),
            LendingTerm.LendingTermReferences({
                profitManager: address(profitManager),
                guildToken: address(guild),
                auctionHouse: address(auctionHouse),
                creditMinter: address(rlcm),
                creditToken: address(credit)
            }),
            LendingTerm.LendingTermParams({
                collateralToken: address(collateral),
                maxDebtPerCollateralToken: _CREDIT_PER_COLLATERAL_TOKEN,
                interestRate: _INTEREST_RATE,
                maxDelayBetweenPartialRepay: _MAX_DELAY_BETWEEN_PARTIAL_REPAY,
                minPartialRepayPercent: _MIN_PARTIAL_REPAY_PERCENT,
                openingFee: 0,
                hardCap: _HARDCAP
            })
        );
        psm = new SimplePSM(
            address(core),
            address(profitManager),
            address(credit),
            address(pegToken)
        );
        profitManager.initializeReferences(address(credit), address(guild), address(psm));

        // roles
        core.grantRole(CoreRoles.GOVERNOR, governor);
        core.grantRole(CoreRoles.GUARDIAN, guardian);
        core.grantRole(CoreRoles.CREDIT_MINTER, address(this));
        core.grantRole(CoreRoles.GUILD_MINTER, address(this));
        core.grantRole(CoreRoles.GAUGE_ADD, address(this));
        core.grantRole(CoreRoles.GAUGE_REMOVE, address(this));
        core.grantRole(CoreRoles.GAUGE_PARAMETERS, address(this));
        core.grantRole(CoreRoles.CREDIT_MINTER, address(rlcm));
        core.grantRole(CoreRoles.RATE_LIMITED_CREDIT_MINTER, address(term));
        core.grantRole(CoreRoles.GAUGE_PNL_NOTIFIER, address(term));
        core.grantRole(CoreRoles.CREDIT_MINTER, address(psm));
        core.grantRole(CoreRoles.CREDIT_REBASE_PARAMETERS, address(psm));
        core.renounceRole(CoreRoles.GOVERNOR, address(this));

        // add gauge 
        guild.setMaxGauges(10);
        guild.addGauge(1, address(term));
    }

    function testBadDebtCreatesBadDebt() public {
        // staker increases term debtCeiling
        guild.mint(staker, 1000e18);
        vm.startPrank(staker);
        guild.incrementGauge(address(term), 1000e18);
        vm.stopPrank();

        assertEq(guild.getGaugeWeight(address(term)), 1000e18);

        // term has 12 active loans all with various borrow sizes (1_000_000 in total loans)
        // 1st loan = 80_000e18
        collateral.mint(borrower, 1_000_000e18);
        uint256[] memory borrowAmounts = new uint256[](11);
        bytes32[] memory loanIds = new bytes32[](11);
        borrowAmounts[0] = 1_000e18;
        borrowAmounts[1] = 5_000e18;
        borrowAmounts[2] = 10_000e18;
        borrowAmounts[3] = 25_000e18;
        borrowAmounts[4] = 100_000e18;
        borrowAmounts[5] = 50_000e18;
        borrowAmounts[6] = 300_000e18;
        borrowAmounts[7] = 18_000e18;
        borrowAmounts[8] = 90_000e18;
        borrowAmounts[9] = 250_000e18;
        borrowAmounts[10] = 71_000e18;

        vm.prank(borrower);
        collateral.approve(address(term), 1_000_000e18);

        // create 1st loan (loan that will create bad debt)
        bytes32 loanId;
        vm.startPrank(borrower);
        loanId = term.borrow(80_000e18, 80_000e18);
        vm.roll(block.number + 1);
        vm.warp(block.timestamp + 13);
        vm.stopPrank();

        // create the rest of the loans (loans that will be forced to create bad debt)
        for (uint256 i; i < borrowAmounts.length; i++) {
            vm.startPrank(borrower);
            loanIds[i] = term.borrow(borrowAmounts[i], borrowAmounts[i]);
            vm.roll(block.number + 1);
            vm.warp(block.timestamp + 13);
            vm.stopPrank();
        }
        
        assertEq(term.issuance(), 1_000_000e18);
        assertEq(credit.balanceOf(borrower), 1_000_000e18);
        assertEq(credit.totalSupply(), 1_000_000e18);

        // lenders supply 1_000_000 pegToken in psm (credit.totalSupply == 2_000_000)
        pegToken.mint(lender, 1_000_000e18);
        vm.startPrank(lender);
        pegToken.approve(address(psm), 1_000_000e18);
        psm.mintAndEnterRebase(1_000_000e18);
        vm.stopPrank();

        assertEq(credit.totalSupply(), 2_000_000e18);

        // half a year later all loans accrued ~2% interest
        vm.warp(block.timestamp + (term.YEAR() / 2));
        
        // term is offboarded 
        guild.removeGauge(address(term));
        assertEq(guild.isGauge(address(term)), false);

        // one loan is called before the others and it creates bad debt (markdown > % interest owed by other loans)
        term.call(loanId);

        // no ones bids and loan creates bad debt (worse case scenario)
        vm.warp(block.timestamp + auctionHouse.auctionDuration());
        (, uint256 creditAsked) = auctionHouse.getBidDetail(loanId); 
        assertEq(creditAsked, 0); // phase 2 ended

        // all loans called via callMany right before bad debt + markdown occurs 
        // to demonstrate that any auctions live while markdown occurred would be affected (including auctions in diff terms)
        term.callMany(loanIds);

        // bad debt created, i.e. markdown of 4%
        // note that for demonstration purposes there are no surplus buffers
        auctionHouse.forgive(loanId);

        assertEq(term.issuance(), 1_000_000e18 - 80_000e18);
        assertEq(credit.totalSupply(), 2_000_000e18);
        assertEq(profitManager.creditMultiplier(), 0.96e18); // credit marked down

        // no one can bid during phase 1 of any other loans that were in auction when the markdown occurred
        // due to principle > creditFromBidder, therefore collateral to borrower must be 0, i.e. all collateral is offered, i.e. must be phase 2
        for (uint256 i; i < loanIds.length; i++) {
            ( , creditAsked) = auctionHouse.getBidDetail(loanIds[i]);
            // verify we are in phase 1 (creditAsked == callDebt)
            assertEq(auctionHouse.getAuction(loanIds[i]).callDebt, creditAsked);
            // attempt to bid during phase 1
            credit.mint(address(this), creditAsked);
            credit.approve(address(term), creditAsked);
            vm.expectRevert("LendingTerm: invalid collateral movement");
            auctionHouse.bid(loanIds[i]);
        }

        // fast forward to the beginning of phase 2
        vm.warp(block.timestamp + auctionHouse.midPoint());
        vm.roll(block.number + 1);

        // all other loans that are in auction will be forced to only receive bids in phase 2
        // bad debt is gauranteed to be created for all these loans, so user's are incentivized to 
        // bid at the top of phase 2. This would result in the liquidator receiving the collateral at a discount. 
        // The loans with less accrued interest and a bigger principle/borrow amount will result in a bigger loss, i.e. greater markdown

        emit log_named_uint("creditMultiplier before updates", profitManager.creditMultiplier());
        
        uint256 collateralReceived;
        for (uint256 i; i < loanIds.length; i++) {
            (collateralReceived, creditAsked) = auctionHouse.getBidDetail(loanIds[i]);
            // verify we are at the top of phase 2 (collateralReceived == collateralAmount | creditAsked == callDebt)
            assertEq(auctionHouse.getAuction(loanIds[i]).callDebt, creditAsked);
            assertEq(auctionHouse.getAuction(loanIds[i]).collateralAmount, collateralReceived);
            // bid at top of phase two (bidder receives collateral at a discount & protocol incurs more bad debt)
            credit.mint(address(this), creditAsked);
            credit.approve(address(term), creditAsked);
            auctionHouse.bid(loanIds[i]);
            multiplierUpdated();
        }
    }

    function multiplierUpdated() internal {
        // credit multiiplier decreases which each auction
        uint256 multiiplier = profitManager.creditMultiplier();

        emit log_named_uint("creditMultiplier updated", multiiplier);
    }
}
```

## Recommendation

`Credit` debt is calculated in most areas of the system with respect to the current multiplier, except for during the auction process. I would suggest calculating the `callDebt` dynamically with respect to the current `creditMultiplier` during the auction process instead of having it represent a ‘snapshot’ of the borrower’s debt.

_Note: For full discussion, see[here](https://github.com/code-423n4/2023-12-ethereumcreditguild-findings/issues/476)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical accounting error that occurs during the liquidation auction of an under‑collateralised loan. The protocol records the borrower’s outstanding debt in a field called callDebt at the moment the loan is flagged for auction. This value is calculated using the creditMultiplier that was current when the loan was called. However, the creditMultiplier can change later when the system records bad debt and marks down the value of the Credit token. Because callDebt is a static snapshot, any subsequent markdown makes the actual debt (principal adjusted by the new multiplier) larger than the stored callDebt. During the first phase of the auction the contract expects bidders to supply exactly callDebt amount of Credit in exchange for a portion of the collateral. If the updated principal exceeds callDebt, the onBid logic computes a negative profit‑and‑loss (pnl) value and reverts unless the collateral to return to the borrower is zero – a condition that only holds in the second phase when the entire collateral is offered. Consequently, bids can only succeed in the second phase, forcing liquidators to accept the full collateral for a reduced Credit payment and creating additional bad debt for the protocol. The impact is that the protocol may lose value because the debt owed is understated, users see their collateral sold at a discount, and the system’s accounting invariants are broken. The issue manifests whenever a markdown of Credit larger than the accrued interest on existing loans occurs while those loans are already in auction. It affects borrowers (who may lose more collateral than expected), lenders (who receive less repayment), and the protocol’s overall solvency. The flaw was discovered through static analysis of the getLoanDebt and onBid functions and confirmed with a targeted test that simulates a markdown during an active auction. It is hard to notice because the callDebt field appears correct at the time of the call and the auction proceeds normally until the markdown changes the multiplier, at which point only the second phase behaves differently. The bug belongs to the class of snapshot‑state‑stale‑value vulnerabilities where a value is cached and not refreshed after a dependent global parameter changes. To fix the issue the protocol should recompute the debt against the current creditMultiplier at each step of the auction rather than relying on a stored snapshot, or alternatively update callDebt dynamically whenever the multiplier changes, ensuring that the amount of Credit required from bidders always reflects the true outstanding debt.
