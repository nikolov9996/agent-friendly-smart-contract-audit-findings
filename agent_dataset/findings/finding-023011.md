---
id: 23011
severity: "High"
---

# Voting does not take into account end of stak-

## Description

The protocol allows to vote in Voter contract by means of staked position in MlumStaking. To vote, user must have staking position with certain properties.
However, the voting does not implement check against invariant that the remaining lock period needs to be longer then the epoch time to be eligible for voting. Thus, it is possible to vote with stale voting position. Additionally, if position's lock period finishes inside of the voting epoch it is possible to vote, withdraw staked position, stake and vote again in the same epoch. Thus, voting twice with the same stake amount is possible from time to time. Ultimately, the invariant that voting once with same balance is only allowed is broken as well. The voting will decide which pools receive LUM emissions and how much.

The documentation states that:
Who is allowed to vote? Only valid Magic LUM Staking Position are allowed to vote. The overall lock needs to be longer then 90 days and the remaining lock period needs to be longer then the epoch time.

User who staked position in the MlumStaking contract gets NFT minted as a proof of stake with properties describing this stake. Then, user can use that staking position to vote for pools by means of vote() in Voter contract. The vote() functions checks if initialLockDuration is higher than _minimumLockTime and lockDuration is higher than _periodDuration to process further. However, it does not check whether the remaining lock period is longer than the epoch time. Thus, it is possible to vote with stale staking position. Also, current implementation makes renewLockPosition and extendLockPosition functions useless.

```solidity
function vote(uint256 tokenId, address[] calldata pools, uint256[] calldata deltaAmounts) external {
    if (pools.length != deltaAmounts.length) revert IVoter__InvalidLength();
    // check voting started
    if (!_votingStarted()) revert IVoter_VotingPeriodNotStarted();
    if (_votingEnded()) revert IVoter_VotingPeriodEnded();
    // check ownership of tokenId
    if (_mlumStaking.ownerOf(tokenId) != msg.sender) {
        revert IVoter__NotOwner();
    }
    uint256 currentPeriodId = _currentVotingPeriodId;
    // check if already voted
    if (_hasVotedInPeriod[currentPeriodId][tokenId]) {
        revert IVoter__AlreadyVoted();
    }
    // check if _minimumLockTime >= initialLockDuration and it is locked
    if (_mlumStaking.getStakingPosition(tokenId).initialLockDuration < _minimumLockTime) {
        revert IVoter__InsufficientLockTime();
    }
    if (_mlumStaking.getStakingPosition(tokenId).lockDuration < _periodDuration) {
        revert IVoter__InsufficientLockTime();
    }
    uint256 votingPower = _mlumStaking.getStakingPosition(tokenId).amountWithMultiplier;
    // check if deltaAmounts > votingPower
    uint256 totalUserVotes;
    for (uint256 i = 0; i < pools.length; ++i) {
        totalUserVotes += deltaAmounts[i];
    }
    if (totalUserVotes > votingPower) {
        revert IVoter__InsufficientVotingPower();
    }
    IVoterPoolValidator validator = _poolValidator;
    for (uint256 i = 0; i < pools.length; ++i) {
        address pool = pools[i];
        if (address(validator) != address(0) && !validator.isValid(pool)) {
            revert Voter__PoolNotVotable();
        }
        uint256 deltaAmount = deltaAmounts[i];
        _userVotes[tokenId][pool] += deltaAmount;
        _poolVotesPerPeriod[currentPeriodId][pool] += deltaAmount;
        if (_votes.contains(pool)) {
            _votes.set(pool, _votes.get(pool) + deltaAmount);
        } else {
            _votes.set(pool, deltaAmount);
        }
        _notifyBribes(_currentVotingPeriodId, pool, tokenId, deltaAmount); // msg.sender, deltaAmount);
    }
    _totalVotes += totalUserVotes;
    _hasVotedInPeriod[currentPeriodId][tokenId] = true;
    emit Voted(tokenId, currentPeriodId, pools, deltaAmounts);
}
```
The documentation states that minimum lock period for staking to be eligible for voting is 90 days. The documentation states that voting for pools occurs biweekly.
Thus, assuming the implementation with configuration presented in the documentation, every 90 days it is possible to vote twice within the same voting epoch by:
• voting,
• withdrawing staked amount,
• creating new position with staking token,
• voting again.

```solidity
function createPosition(uint256 amount, uint256 lockDuration) external override nonReentrant {
    // no new lock can be set if the pool has been unlocked
    if (isUnlocked()) {
        require(lockDuration == 0, "locks disabled");
    }
    _updatePool();
    // handle tokens with transfer tax
    amount = _transferSupportingFeeOnTransfer(stakedToken, msg.sender, amount);
    require(amount != 0, "zero amount"); // createPosition: amount cannot be null
    // mint NFT position token
    uint256 currentTokenId = _mintNextTokenId(msg.sender);
    // calculate bonuses
    uint256 lockMultiplier = getMultiplierByLockDuration(lockDuration);
    uint256 amountWithMultiplier = amount * (lockMultiplier + 1e4) / 1e4;
    // create position
    _stakingPositions[currentTokenId] = StakingPosition({
        initialLockDuration: lockDuration,
        amount: amount,
        rewardDebt: amountWithMultiplier * (_accRewardsPerShare) / (PRECISION_FACTOR),
        lockDuration: lockDuration,
        startLockTime: _currentBlockTimestamp(),
        lockMultiplier: lockMultiplier,
        amountWithMultiplier: amountWithMultiplier,
        totalMultiplier: lockMultiplier
    });
    // update total lp supply
    _stakedSupply = _stakedSupply + amount;
    _stakedSupplyWithMultiplier = _stakedSupplyWithMultiplier + amountWithMultiplier;
    emit CreatePosition(currentTokenId, amount, lockDuration);
}
```
A user can vote with stale staking position, then withdraw the staking position with any consequences. Additionally, a user can periodically vote twice with the same balance of staking tokens for the same pool to increase unfairly the chance of the pool being selected for further processing.

## Proof of Concept

Scenario 1:
```solidity
function testGT_vote_twice_with_the_same_stake() public {
    vm.prank(DEV);
    _voter.updateMinimumLockTime(2 weeks);
    _stakingToken.mint(ALICE, 1 ether);
    vm.startPrank(ALICE);
    _stakingToken.approve(address(_pool), 1 ether);
    _pool.createPosition(1 ether, 2 weeks);
    vm.stopPrank();
    skip(1 weeks);
    vm.prank(DEV);
    _voter.startNewVotingPeriod();
    vm.startPrank(ALICE);
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    vm.expectRevert(IVoter.IVoter__AlreadyVoted.selector);
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    vm.stopPrank();
    assertEq(_voter.getTotalVotes(), 1 ether);
    skip(1 weeks + 1);
    vm.startPrank(ALICE);
    _pool.withdrawFromPosition(1, 1 ether);
    vm.stopPrank();
    vm.startPrank(ALICE);
    vm.expectRevert();
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    _stakingToken.approve(address(_pool), 1 ether);
    _pool.createPosition(1 ether, 2 weeks);
    _voter.vote(2, _getDummyPools(), _getDeltaAmounts());
    vm.stopPrank();
    assertEq(_voter.getTotalVotes(), 2 ether);
}
```
Scenario 2:
```solidity
function testGT_vote_twice_with_the_same_stake() public {
    vm.prank(DEV);
    _voter.updateMinimumLockTime(2 weeks);
    _stakingToken.mint(ALICE, 1 ether);
    vm.startPrank(ALICE);
    _stakingToken.approve(address(_pool), 1 ether);
    _pool.createPosition(1 ether, 2 weeks);
    vm.stopPrank();
    skip(1 weeks);
    vm.prank(DEV);
    _voter.startNewVotingPeriod();
    vm.startPrank(ALICE);
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    vm.expectRevert(IVoter.IVoter__AlreadyVoted.selector);
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    vm.stopPrank();
    assertEq(_voter.getTotalVotes(), 1 ether);
    skip(1 weeks + 1);
    vm.startPrank(ALICE);
    _pool.withdrawFromPosition(1, 1 ether);
    vm.stopPrank();
    vm.startPrank(ALICE);
    vm.expectRevert();
    _voter.vote(1, _getDummyPools(), _getDeltaAmounts());
    _stakingToken.approve(address(_pool), 1 ether);
    _pool.createPosition(1 ether, 2 weeks);
    _voter.vote(2, _getDummyPools(), _getDeltaAmounts());
    vm.stopPrank();
    assertEq(_voter.getTotalVotes(), 2 ether);
}
```

## Recommendation

It is recommended to enforce the invariant that the remaining lock period must be longer than the epoch time to be eligible for voting. Additionally, it is recommended to prevent double voting at any time. One of the solution can be to prevent voting within the epoch if staking position was not created before epoch started.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the voting logic of the Voter contract, which accepts a staking position as proof of voting power but fails to verify that the remaining lock period of that position exceeds the length of the current voting epoch. The protocol documentation requires that a valid Magic LUM staking position must have an overall lock longer than 90 days and that the remaining lock time be longer than the epoch duration, yet the contract only checks the initial lock duration and the total lock duration at the moment of voting. Consequently, a user can submit a vote with a stale position whose lock has already expired or will expire during the epoch. After casting a vote, the user can withdraw the original position, create a new staking position with the same amount of tokens, and cast a second vote within the same epoch because the contract only records a single vote per tokenId per period and does not consider that the tokenId may have been destroyed and replaced. This breaks the invariant that each stake may vote only once per epoch and allows double‑voting with the same balance, inflating the vote weight of chosen pools. The impact is that pool selection for LUM emissions can be manipulated, giving an unfair advantage to parties that exploit the timing loophole. The issue occurs whenever a staking position satisfies the minimum lock requirement but its remaining lock is shorter than the epoch, which can happen every 90 days for a 2‑week lock configuration. It affects any user holding a staking NFT, the protocol’s governance outcomes, and ultimately the fairness of token emissions. The flaw was discovered during a security audit that compared the on‑chain checks with the documented requirements and reproduced the exploit in unit tests. It is hard to notice because the contract does emit no explicit error for a stale lock, and the UI may simply show a successful vote while the underlying lock condition is violated. To remediate, the contract must enforce the invariant that the remaining lock period is greater than the epoch length before accepting a vote, and it should prevent voting with a position that was created after the epoch started or that has been withdrawn and re‑created within the same epoch. This can be achieved by adding a check against the current block timestamp and the position’s startLockTime, and by tracking votes per address or per stake lifecycle rather than only per tokenId per period. The fix restores the intended business logic that each stake can contribute voting power exactly once per epoch, preserving the fairness of pool selection and emission distribution.
