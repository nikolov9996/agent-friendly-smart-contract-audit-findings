---
id: 18411
severity: "High"
---

# `ReraiseETHCrowdfund.sol`: Multiple scenarios how pending votes might not be claimable which is a complete loss of funds for a user

## Description

This issue is about how the [`ReraiseETHCrowdfund`](https://github.com/code-423n4/2023-04-party/blob/main/contracts/crowdfund/ReraiseETHCrowdfund.sol) claim functionality can be broken.

When the claim functionality is broken this means that a user cannot claim his voting power, resulting in a complete loss of funds.

The claim functionality is not broken in any case, i.e. with any configuration of the `ReraiseETHCrowdfund` contract.

However the contract can be configured in a way - and by configured I mean specifically the `minContribution`, `maxContribution`, `minTotalContributions` and `maxTotalContributions` variables - that the claim functionality breaks.

And the configurations under which it breaks are NOT edge cases. They represent the **intended use** of the contract as discussed with the sponsor.

The fact that when the contract is used as intended it can lead to a complete loss of funds for the users makes me estimate this to be “High” severity.

## Proof of Concept

We first need to understand the `claim(uint256 tokenId, address contributor)` and `claimMultiple(uint96[] memory votingPowerByCard, address contributor)` functions. They essentially make up the claim functionality as all other functions regarding claiming are just wrappers around them.

Let’s first look at the `claim(uint256 tokenId, address contributor)` function. The first part of the function is what we are interested in:
[Link](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ReraiseETHCrowdfund.sol#L256-L283)
```solidity
function claim(uint256 tokenId, address contributor) public {
    // Check crowdfund lifecycle.
    {
        CrowdfundLifecycle lc = getCrowdfundLifecycle();
        if (lc != CrowdfundLifecycle.Finalized) {
            revert WrongLifecycleError(lc);
        }
    }

    uint96 votingPower = pendingVotingPower[contributor];

    if (votingPower == 0) return;

    {
        uint96 contribution = (votingPower * 1e4) / exchangeRateBps;
        uint96 maxContribution_ = maxContribution;
        // Check that the contribution equivalent of total pending voting
        // power is not above the max contribution range. This can happen
        // for contributors who contributed multiple times In this case, the
        // `claimMultiple` function should be called instead. This is done
        // so parties may use the minimum and maximum contribution values to
        // limit the voting power of each card (e.g. a party desiring a "1
        // card = 1 vote"-like governance system where each card has equal
        // voting power).
        if (contribution > maxContribution_) {
            revert AboveMaximumContributionsError(contribution, maxContribution_);
        }
    }
```

What is important is that `contribution` is calculated as:
```solidity
uint96 contribution = (votingPower * 1e4) / exchangeRateBps;
```
And then `contribution` is checked that it is `<= maxContribution`:
```solidity
if (contribution > maxContribution_) {
    revert AboveMaximumContributionsError(contribution, maxContribution_);
}
```
The explanation for why this check is necessary can be seen in the comment:
```solidity
// This is done
// so parties may use the minimum and maximum contribution values to
// limit the voting power of each card (e.g. a party desiring a "1
// card = 1 vote"-like governance system where each card has equal
// voting power).
```

The `claimMultiple(uint96[] memory votingPowerByCard, address contributor)` function allows to divide the pending voting power across multiple party cards and it employs the following checks:
[Link](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ReraiseETHCrowdfund.sol#L352-L382)
```solidity
uint96 minContribution_ = minContribution;
uint96 maxContribution_ = maxContribution;
for (uint256 i; i < votingPowerByCard.length; ++i) {
    if (votingPowerByCard[i] == 0) continue;

    // Check that the contribution equivalent of voting power is within
    // contribution range. This is done so parties may use the minimum
    // and maximum contribution values to limit the voting power of each
    // card (e.g. a party desiring a "1 card = 1 vote"-like governance
    // system where each card has equal voting power).
    uint96 contribution = (votingPowerByCard[i] * 1e4) / exchangeRateBps;
    if (contribution < minContribution_) {
        revert BelowMinimumContributionsError(contribution, minContribution_);
    }

    if (contribution > maxContribution_) {
        revert AboveMaximumContributionsError(contribution, maxContribution_);
    }

    votingPower -= votingPowerByCard[i];

    // Mint contributor a new party card.
    uint256 tokenId = party.mint(contributor, votingPowerByCard[i], delegate);

    emit Claimed(contributor, tokenId, votingPowerByCard[i]);
}

// Requires that all voting power is claimed because the contributor is
// expected to have burned their crowdfund NFT.
if (votingPower != 0) revert RemainingVotingPowerAfterClaimError(votingPower);
```
We can see that for each party card the `contribution` needs to be `>= minContribution` and `<= maxContribution`. Also the function must deal with all the voting power, so after the function call all pending voting power must be processed:
```solidity
if (votingPower != 0) revert RemainingVotingPowerAfterClaimError(votingPower);
```
Now we are in a position to look at a simple scenario how a user can end up without being able to claim his pending voting power (Note that this can also be a griefing attack whereby an attacker contributes for the victim some possibly small amount thereby making it impossible for the victim to claim):

(The test should be added to the `ReraiseETHCrowdfund.t.sol` test file)
```solidity
function test_cannotClaim1() public {
    ReraiseETHCrowdfund crowdfund = _createCrowdfund({
        initialContribution: 0,
        initialContributor: payable(address(0)),
        initialDelegate: address(0),
        minContributions: 0.9 ether,
        maxContributions: 1 ether,
        disableContributingForExistingCard: false,
        minTotalContributions: 1 ether,
        maxTotalContributions: 1.5 ether,
        duration: 7 days,
        fundingSplitBps: 0,
        fundingSplitRecipient: payable(address(0))
    });

    address member = _randomAddress();
    vm.deal(member, 2 ether);

    // Contribute
    vm.startPrank(member);
    crowdfund.contribute{ value: 1 ether }(member, "");
    crowdfund.contribute{ value: 1 ether }(member, "");
    vm.stopPrank();

    assertEq(crowdfund.pendingVotingPower(member), 1.5 ether);

    vm.expectRevert(
        abi.encodeWithSelector(
            ETHCrowdfundBase.AboveMaximumContributionsError.selector,
            1500000000000000000,
            1000000000000000000
        )
    );
    crowdfund.claim(member);
}
```
In this test the following values were chosen for the important variables that I mentioned above:
```solidity
minContribution = 0.9e18
maxContribution = 1e18

minTotalContributions = 1e18
maxTotalContributions = 1.5e18
```
What happens in the test is that first `1 ETH` is contributed then another `0.5 ETH` is contributed (It says `1 ETH` but `maxTotalContributions` is hit and so only `0.5 ETH` is contributed and the crowdfund is finalized).

The call to the `claim` function fails because `contribution = 1.5 ETH` which is above `maxContribution`.

The important thing is now to understand that `claimMultiple` can also not be called (therefore the pending voting power cannot be claimed at all).

When we call `claimMultiple` the contribution for the first party card must be in the range `[0.9e18, 1e18]` to succeed and therefore the second contribution can only be in the range of `[0.5e18,0.6e18]` which is below `minContribution` and therefore it is not possible to distribute the voting power across cards such that the call succeeds.

What we discussed so far could be mitigated by introducing some simple checks when setting up the crowdfund. The sort of checks required are like ”`minTotalContributions` must be divisible by `minContribution`”. I won’t go into this deeply however because these checks are insufficient when we introduce a funding fee.

Let’s consider a case with:
```solidity
minContribution = 1e18
maxContribution = 1e18
minTotalContributions = 2e18
maxTotalContributions = 2e18
```
(Note that setting up the crowdfund with `minContribution==maxContribution` is an important use case where the party wants to enforce a “1 card = 1 vote”-policy).

There should be no way how this scenario causes a problem right? The contribution of a user can only be `1e18` or `2e18` and in both cases the checks in the claim functions should pass. - No

It breaks when we introduce a fee. Say there is a 1% fee (`fundingSplitBps=100`).

The contribution is calculated as (as we know from above):
```solidity
uint96 contribution = (votingPower * 1e4) / exchangeRateBps;
```
Also note that `exchangeRateBps=1e4` for all tests, i.e. the exchange rate between ETH and votes is 1:1)

The problem is that `votingPower` has been reduced by 1% due to the funding fee. So when a user initially contributes `1e18`, the `contribution` here is calculated to be `0.99e18 * 1e4 / 1e4 = 0.99e18` which is below `minContribution` and claiming is not possible.

Let’s make a final observation: The parameters can also be such that due to rounding a similar thing happens:
```solidity
minContribution = 1e18 + 1 wei
maxContribution = 1e18 + 1 wei
minTotalContributions = 2e18 + 2 wei
maxTotalContributions = 2e18 + 2 wei
```
Due to rounding (when calculating the funding fee or when there is not a 1:1 exchange rate) the 1 wei in the contribution can be lost (or some other small amount) and thereby when calling `claim`, the `contribution` which has been rounded down is below `minContribution` and the claim fails.

To summarize we have seen 3 scenarios. It is not possible for me to provide an overview of all the things that can go wrong. There are just too many variables. I come back to this point in my recommendation.

## Recommendation

A part of the fix is straightforward. However this is not a full fix.

I recommend to implement a functionality for claiming that cannot be blocked. I know that this may cause the “1 card = 1 vote”-policy to be violated and it may also cause `minContribution` or `maxContribution` to be violated. But maybe this is the price to pay to ensure that users can always claim.

An alternative solution may be to reduce the range of possible configurations of the crowdfund drastically such that it can be mathematically proven that users are always able to claim.

That being said there is an obvious flaw in the current code that has been confirmed by the sponsor.

The `contribution` amount that is calculated when claiming needs to add back the funding fee amount. I.e. if there was a 1% funding fee, the `contribution` amount should be `1e18` instead of `0.99e18`.

Partial fix:
```diff
diff --git a/contracts/crowdfund/ReraiseETHCrowdfund.sol b/contracts/crowdfund/ReraiseETHCrowdfund.sol
index 580623d..0b1ba9e 100644
--- a/contracts/crowdfund/ReraiseETHCrowdfund.sol
+++ b/contracts/crowdfund/ReraiseETHCrowdfund.sol
@@ -268,6 +268,13 @@ contract ReraiseETHCrowdfund is ETHCrowdfundBase, CrowdfundNFT {
 
         {
             uint96 contribution = (votingPower * 1e4) / exchangeRateBps;
+
             address payable fundingSplitRecipient_ = fundingSplitRecipient;
             uint16 fundingSplitBps_ = fundingSplitBps;
             if (fundingSplitRecipient_ != address(0) && fundingSplitBps_ > 0) {
                 contribution = (contribution * 1e4) / (1e4 - fundingSplitBps_);
             }
+
             uint96 maxContribution_ = maxContribution;
             // Check that the contribution equivalent of total pending voting
             // power is not above the max contribution range. This can happen
@@ -360,6 +367,13 @@ contract ReraiseETHCrowdfund is ETHCrowdfundBase, CrowdfundNFT {
             // card (e.g. a party desiring a "1 card = 1 vote"-like governance
             // system where each card has equal voting power).
             uint96 contribution = (votingPowerByCard[i] * 1e4) / exchangeRateBps;
+
             address payable fundingSplitRecipient_ = fundingSplitRecipient;
             uint16 fundingSplitBps_ = fundingSplitBps;
             if (fundingSplitRecipient_ != address(0) && fundingSplitBps_ > 0) {
                 contribution = (contribution * 1e4) / (1e4 - fundingSplitBps_);
             }
+
             if (contribution < minContribution_) {
                 revert BelowMinimumContributionsError(contribution, minContribution_);
             }
```

Additional to the partial fix recommended in the mitigation, this will be mitigated by [preventing the case where `minContribution` may be bypassed for the last contributor when the remaining contribution is less than the minimum](https://github.com/code-423n4/2023-04-party-findings/issues/37#issuecomment-1526104629).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the claim workflow of the ReraiseETHCrowdfund contract where a contributor’s pending voting power is converted back into an ETH contribution using a simple division by the exchange rate. This conversion ignores the funding fee that was deducted from the original contribution and also does not account for rounding effects, causing the derived contribution amount to fall outside the contract‑defined minimum and maximum contribution limits. When the calculated contribution exceeds maxContribution, the single‑claim function reverts with an AboveMaximumContributionsError; when it falls below minContribution, the multi‑claim function reverts with a BelowMinimumContributionsError. Because the contract enforces that all pending voting power must be claimed either in a single claim or split across multiple cards, a situation where the contribution cannot satisfy both bounds makes the claim permanently impossible. This can happen under normal, intended configurations of minContribution, maxContribution, minTotalContributions and maxTotalContributions, especially when a non‑zero fundingSplitBps fee is applied or when rounding losses occur. An attacker can deliberately contribute a small amount that pushes the victim’s pending voting power into a range that violates the bounds, effectively griefing the victim. The impact is that the affected user cannot retrieve their ETH, sees no tokens minted, and experiences transaction reverts, resulting in a complete loss of funds. The issue manifests after the crowdfund reaches the Finalized lifecycle and a contributor attempts to claim. It affects any participant who has pending voting power, the protocol’s economic guarantees, and the overall trustworthiness of the fundraising mechanism. The problem was discovered during a security audit by Code4rena through systematic testing of the claim functions with various parameter combinations, revealing that the invariant “contribution must lie within [minContribution, maxContribution]” is not preserved after fee deduction and rounding. The bug is subtle because the arithmetic appears correct at first glance and only fails for specific, non‑edge‑case configurations, making it hard to notice in casual testing. To remediate, the contribution calculation must be adjusted to add back the funding fee, ensuring the resulting amount respects the configured bounds, and the contract should either relax the claim‑blocking checks or enforce stricter configuration validation that guarantees a feasible claim path for any pending voting power. In broader terms, this is a parameter‑validation mismatch and rounding‑induced invariant violation that blocks a critical user‑facing operation, violating the expected business logic that contributors can always retrieve their funds after a successful crowdfund.
