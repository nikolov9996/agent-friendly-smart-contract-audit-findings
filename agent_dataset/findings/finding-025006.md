---
id: 25006
severity: "Medium"
---

# Delegate rewards system is unfair to delegates with less tokens and reduces decentralization

## Description



## Proof of Concept

The current math gives delegates rewards based on the square of their votes. Thus, accounts with higher number of votes will be rewarded a bigger number of rewards, leading to less decentralization.

Add the following test to `StandardFunding.t.sol`

function test_POC_WhaleCanStealMostDelegateRewards() external { // 24 tokenholders self delegate their tokens to enable voting on the proposals _selfDelegateVoters(_token, _votersArr);

changePrank(_tokenDeployer); _token.transfer(_tokenHolder1, 300_000_000 * 1e18);

vm.roll(_startBlock + 150);

// start distribution period _startDistributionPeriod(_grantFund);

uint24 distributionId = _grantFund.getDistributionId();

(, , , uint128 gbc, , ) = _grantFund.getDistributionPeriodInfo(distributionId);

assertEq(gbc, 15_000_000 * 1e18);

TestProposalParams[] memory testProposalParams = new TestProposalParams[](1); testProposalParams[0] = TestProposalParams(_tokenHolder1, 8_500_000 * 1e18);

// create 7 proposals paying out tokens TestProposal[] memory testProposals = _createNProposals(_grantFund, _token, testProposalParams); assertEq(testProposals.length, 1);

vm.roll(_startBlock + 200);

// screening period votes _screeningVote(_grantFund, _tokenHolder1, testProposals[0].proposalId, _getScreeningVotes(_grantFund, _tokenHolder1)); _screeningVote(_grantFund, _tokenHolder2, testProposals[0].proposalId, _getScreeningVotes(_grantFund, _tokenHolder2));

/*********************/ /*** Funding Stage ***/ /*********************/

// skip time to move from screening period to funding period vm.roll(_startBlock + 600_000);

// check topTenProposals array is correct after screening period - only six should have advanced GrantFund.Proposal[] memory screenedProposals = _getProposalListFromProposalIds(_grantFund, _grantFund.getTopTenProposals(distributionId));

// funding period votes for two competing slates, 1, or 2 and 3 _fundingVote(_grantFund, _tokenHolder1, screenedProposals[0].proposalId, voteYes, 350_000_000 * 1e18); _fundingVote(_grantFund, _tokenHolder2, screenedProposals[0].proposalId, voteYes, 50_000_000 * 1e18);

/************************/ /*** Challenge Period ***/ /************************/

uint256[] memory potentialProposalSlate = new uint256[](1); potentialProposalSlate[0] = screenedProposals[0].proposalId;

// skip to the end of the DistributionPeriod vm.roll(_startBlock + 650_000);

vm.expectEmit(true, true, false, true); emit FundedSlateUpdated(distributionId, _grantFund.getSlateHash(potentialProposalSlate)); bool proposalSlateUpdated = _grantFund.updateSlate(potentialProposalSlate, distributionId); assertTrue(proposalSlateUpdated);

/********************************/ /*** Execute Funded Proposals ***/ /********************************/

// skip to the end of the Distribution's challenge period vm.roll(_startBlock + 700_000);

// execute funded proposals _executeProposal(_grantFund, _token, testProposals[0]);

/******************************/ /*** Claim Delegate Rewards ***/ /******************************/

assertEq(_grantFund.getDelegateReward(distributionId, _tokenHolder1) / 1e18, 1_470_000); assertEq(_grantFund.getDelegateReward(distributionId, _tokenHolder2) / 1e18, 30_000);

// _tokenHolder1 reward is approx 1_470_000/(1_470_000 + 30_000) ~ 98%

// linear distribution // _tokenHolder1 reward is approx 350/(350 + 50) = 87.5% }

In this test, `_tokenHolder1` has 350/50 = 7 times more tokens and leads to getting 98% of the rewards. Had a linear distribution been used, `_tokenHolder1` would have received 87.5%, a fairer number.

In fact, it's even better to use a quadratic voting system, being the rewards the square root of the votes. This would incentivize more delegates and increase decentralization.

## Recommendation

Use a linear or [quadratic](<https://axelar.network/blog/quadratic-voting-DAOs-dPoS-and-decentralization>) delegate reward system.
