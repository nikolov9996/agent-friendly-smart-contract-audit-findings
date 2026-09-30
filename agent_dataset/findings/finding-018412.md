---
id: 18412
severity: "High"
---

# `ReraiseETHCrowdfund.sol`: party card transfer can be front-run by claiming pending voting power which results in a loss of the voting power

## Description

In this report I show how an attacker can abuse the fact that anyone can call [`ReraiseETHCrowdfund.claim`](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ReraiseETHCrowdfund.sol#L251-L303) for any user and add voting power to an existing party card.

The result can be a griefing attack whereby the victim loses voting power. In some cases the attacker can take advantage himself.

In short this is what needs to happen:

1. The victim sends a transaction to transfer one of his party cards
2. The transaction is front-run and pending voting power of the victim from the `ReraiseETHCrowdfund` contract is claimed to this party card that is transferred
3. The victim thereby loses the pending voting power

The fact that any user is at risk that has pending voting power and transfers a party card and that voting power is arguably the most important asset in the protocol makes me estimate this to be “High” severity.

## Proof of Concept

We start by observing that when the `ReraiseETHCrowdfund` is won, any user can call `ReraiseETHCrowdfund.claim` for any other user and either mint a new party card to him or add the pending voting power to an existing party card:
[Link](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ReraiseETHCrowdfund.sol#L251-L303)
```solidity
/// @notice Claim a party card for a contributor if the crowdfund won. Can be called
///         to claim for self or on another's behalf.
/// @param tokenId The ID of the party card to add voting power to. If 0, a
///                new card will be minted.
/// @param contributor The contributor to claim for.
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

    // Burn the crowdfund NFT.
    _burn(contributor);

    delete pendingVotingPower[contributor];

    if (tokenId == 0) {
        // Mint contributor a new party card.
        tokenId = party.mint(contributor, votingPower, delegationsByContributor[contributor]);
    } else if (disableContributingForExistingCard) {
        revert ContributingForExistingCardDisabledError();
    } else if (party.ownerOf(tokenId) == contributor) {
        // Increase voting power of contributor's existing party card.
        party.addVotingPower(tokenId, votingPower);
    } else {
        revert NotOwnerError();
    }

    emit Claimed(contributor, tokenId, votingPower);
```
Note that the caller can specify any `contributor` and can add the pending votes to an existing party card if `!disableContributingForExistingCard && party.ownerOf(tokenId) == contributor`.

So if User A has pending voting power and transfers one of his party cards to User B, then User C might front-run this transfer and claim the pending voting power to the party card that is transferred.

If User B performs this attack it is not a griefing attack since User B benefits from it.

Note that at the time of sending the transfer transaction the `ReraiseETHCrowdfund` does not have to be won already. The transaction that does the front-running might contribute to the crowdfund such that it is won and then claim the pending voting power.

Add the following test to the `ReraiseETHCrowdfund.t.sol` test file. It shows how an attacker would perform such an attack:
```solidity
function test_FrontRunTransfer() public {
    ReraiseETHCrowdfund crowdfund = _createCrowdfund({
        initialContribution: 0,
        initialContributor: payable(address(0)),
        initialDelegate: address(0),
        minContributions: 0,
        maxContributions: type(uint96).max,
        disableContributingForExistingCard: false,
        minTotalContributions: 2 ether,
        maxTotalContributions: 3 ether,
        duration: 7 days,
        fundingSplitBps: 0,
        fundingSplitRecipient: payable(address(0))
    });

    address attacker = _randomAddress();
    address victim = _randomAddress();
    vm.deal(victim, 2.5 ether);
    vm.deal(attacker, 0.5 ether);

    // @audit-info the victim owns a party card
    vm.prank(address(party));
    party.addAuthority(address(this));
    party.increaseTotalVotingPower(1 ether);
    uint256 victimTokenId = party.mint(victim, 1 ether, address(0));

    vm.startPrank(victim);
    crowdfund.contribute{ value: 2.5 ether }(victim, "");
    vm.stopPrank();

    /* @audit-info
    The victim wants to transfer the party card, say to the attacker, and the attacker
    front-runs this by completing the crowdfund and claiming the victim's pending voting
    power to the existing party card
    */

    vm.startPrank(attacker);
    crowdfund.contribute{ value: 0.5 ether }(attacker, "");
    crowdfund.claim(victimTokenId,victim);
    vm.stopPrank();

    /* @audit-info
    when the victim's transfer is executed, he transfers also all of the voting power
    that was previously his pending voting power (effectively losing it)
    */
    vm.prank(victim);
    party.transferFrom(victim,attacker,victimTokenId);
}
```
So when there is an ongoing crowdfund it is never safe to transfer one’s party card. It can always result in a complete loss of the pending voting power.

## Recommendation

In the `ReraiseETHCrowdfund.claim` function it should not be possible to add the pending voting power to an existing party card. It is possible though to allow it for the `contributor` himself but not for any user.
```diff
diff --git a/contracts/crowdfund/ReraiseETHCrowdfund.sol b/contracts/crowdfund/ReraiseETHCrowdfund.sol
index 580623d..cb560e1 100644
--- a/contracts/crowdfund/ReraiseETHCrowdfund.sol
+++ b/contracts/crowdfund/ReraiseETHCrowdfund.sol
@@ -292,7 +292,7 @@ contract ReraiseETHCrowdfund is ETHCrowdfundBase, CrowdfundNFT {
             tokenId = party.mint(contributor, votingPower, delegationsByContributor[contributor]);
         } else if (disableContributingForExistingCard) {
             revert ContributingForExistingCardDisabledError();
-        } else if (party.ownerOf(tokenId) == contributor) {
+        } else if (party.ownerOf(tokenId) == contributor && contributor == msg.sender) {
             // Increase voting power of contributor's existing party card.
             party.addVotingPower(tokenId, votingPower);
         } else {
```

Good finding, still thinking about the mitigation.

Slightly hesitant to make the only action when claiming for someone else to be minting them a new card although minting to their existing card might be a rare action because of the friction involved in having to get the ID of one of the person’s cards first. Someone minting for someone else might just find it more convenient to mint them a new card, so having that be the only action might not be much of a loss.

We’ve decided to refactor the way claiming works in the `ReraiseETHCrowdfund`, partially because a large number of findings like this being submitted around that one area that highlighted for us the need to rework its logic.

The change will make it so (1) crowdfund NFTs are minted per contribution instead of per address and (2) claiming works more like a 1:1 conversion of your crowdfund NFT into a party card instead of how it works now. In the future we will also add the ability to split/merge party cards.

This should mitigate this finding because in this new system you cannot decide to add the voting power from a crowdfund NFT to an existing party card when claiming, only mint a new party card.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a front‑run authorization flaw in the ReraiseETHCrowdfund.claim function that permits any address to claim pending voting power on behalf of any contributor and to add that power to an existing party card owned by the contributor. The root cause is that the function does not restrict the caller to the contributor when the caller supplies a non‑zero tokenId and the party card owner matches the contributor; it only checks that the caller is the owner of the token if the token already belongs to the contributor, but it does not require msg.sender to be the contributor. An attacker can exploit this by observing that a victim has pending voting power in the crowdfund and is about to transfer one of their party cards. The attacker front‑runs the victim’s transfer transaction, calls claim with the victim’s address as the contributor and the tokenId of the card that will be transferred, and thereby adds the pending voting power to that card before the transfer completes. When the victim’s transfer later executes, the card (now owned by the attacker) carries the voting power that originally belonged to the victim, leaving the victim with a transferred card that has no voting power. The impact is a loss of governance weight for the victim, which can be used as a griefing attack or, if the attacker is the recipient, as a direct gain of voting power. The attack can occur whenever a contributor has pending voting power (i.e., after a successful crowdfund) and initiates a transfer of a party card before the pending votes are claimed, and the attacker can submit a transaction that finalizes the crowdfund and calls claim before the transfer is mined. All users who hold party cards and have unclaimed voting power are affected, as voting power is the core asset of the Party protocol’s governance model. The issue was discovered during a security audit when the auditors wrote a test that demonstrated the front‑run scenario. It is hard to notice because the claim function appears to be a benign utility for contributors, and the loss of voting power only becomes visible after a transfer, which may be attributed to other reasons. The recommended fix is to restrict claim so that adding voting power to an existing card is only allowed when the caller is the contributor (msg.sender == contributor) or to disallow adding to existing cards altogether and always mint a new party card on claim. This aligns with the generic class of bugs where a function that should be limited to a privileged actor lacks proper access control, leading to asset misallocation. From the user’s perspective, they expect that after transferring a party card they retain the same amount of voting power, but instead the transferred card arrives with zero votes and the user’s governance weight disappears, violating the protocol’s accounting assumptions that pending voting power remains attached to the contributor until they claim it themselves.
