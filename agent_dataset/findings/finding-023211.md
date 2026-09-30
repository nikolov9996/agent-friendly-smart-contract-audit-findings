---
id: 23211
severity: "High"
---

# The Users who voted for collec-

## Description

When a user votes for collection shutdown, the CollectionShutdown contract gathers the whole balance from the user. However, when cancelling the shutdown process, the contract doesn't refund the user's votes.
The function gathers the whole balance of the collection token from a voter.
```solidity
function _vote(address _collection, CollectionShutdownParams memory params)
    internal returns (CollectionShutdownParams memory) {
    ,→
    uint userVotes = params.collectionToken.balanceOf(msg.sender);
    if (userVotes == 0) revert UserHoldsNoTokens();
    // Pull our tokens in from the user
    params.collectionToken.transferFrom(msg.sender, address(this), userVotes);
}
```
But in the function, it does not refund the voters tokens.
```solidity
function cancel(address _collection) public whenNotPaused {
    // Ensure that the vote count has reached quorum
    CollectionShutdownParams memory params = _collectionParams[_collection];
    if (!params.canExecute) revert ShutdownNotReachedQuorum();
    // Check if the total supply has surpassed an amount of the initial required
    // total supply. This would indicate that a collection has grown since the
    // initial shutdown was triggered and could result in an unsuspected liquidation.
    ,→
    if (params.collectionToken.totalSupply() <= MAX_SHUTDOWN_TOKENS * 10 **
        locker.collectionToken(_collection).denomination()) {
        ,→
        revert InsufficientTotalSupplyToCancel();
    }
    // Remove our execution flag
    delete _collectionParams[_collection];
    emit CollectionShutdownCancelled(_collection);
}
```
Shutdown Voters will be ended up losing their whole collection tokens by cancelling the shutdown.

## Proof of Concept

Here is the testcase of the POC:
To bypass the total supply vs shutdown votes restriction, added the following line to the test case:
```solidity
collectionToken.mint(address(10), _additionalAmount);
```
The whole test case is:
```solidity
function test_CancelShutdownNotRefund() public withQuorumCollection {
    uint256 _additionalAmount = 1 ether;
    // Confirm that we can execute with our quorum-ed collection
    assertCanExecute(address(erc721b), true);
    vm.prank(address(locker));
    collectionToken.mint(address(10), _additionalAmount);
    // Cancel our shutdown
    collectionShutdown.cancel(address(erc721b));
    // Now that we have cancelled the shutdown process, we should no longer
    // be able to execute the shutdown.
    assertCanExecute(address(erc721b), false);
    console.log("Address 1 balance after:", collectionToken.balanceOf(address(1)));
    console.log("Address 2 balance after:", collectionToken.balanceOf(address(2)));
}
```
Here are the logs after running the test:
```bash
$ forge test --match-test test_CancelShutdownNotRefund -vv
[￿] Compiling...
[￿] Compiling 1 files with Solc 0.8.26
[￿] Solc 0.8.26 finished in 8.81s
Compiler run successful!
Ran 1 test for test/utils/CollectionShutdown.t.sol:CollectionShutdownTest
[PASS] test_CancelShutdownNotRefund() (gas: 390566)
Logs:
Address 1 balance after: 0
Address 2 balance after: 0
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 8.29s (454.80µs CPU time)
,→
Ran 1 test suite in 8.29s (8.29s CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
,→
```
As can be seen from the logs, the voters(1, 2) were not refunded their tokens.

## Recommendation

1. Add new state variable to the contract that records all voters
```solidity
address[] public votersList;
```
2. Update the _vote() function like below:
```solidity
function _vote(address _collection, CollectionShutdownParams memory params)
    internal returns (CollectionShutdownParams memory) {
    ,→
    // Register the amount of votes sent as a whole, and store them against the user
    ,→
    params.shutdownVotes += uint96(userVotes);
    // Register the amount of votes for the collection against the user
    +
    if (shutdownVoters[_collection][msg.sender] == 0)
    +
        votersList.push(msg.sender);
    unchecked { shutdownVoters[_collection][msg.sender] += userVotes; }
}
```
3. Add the new code section to the reclaimVote() function, that removes the sender from the votersList.
4. Update the cancel() function like below:
```solidity
function cancel(address _collection) public whenNotPaused {
    if (params.collectionToken.totalSupply() <= MAX_SHUTDOWN_TOKENS * 10 **
        locker.collectionToken(_collection).denomination()) {
        ,→
        revert InsufficientTotalSupplyToCancel();
    }
    +
    uint256 i;
    +
    uint256 votersLength = votersList.length;
    +
    for (; i < votersLength; i ++) {
    +
        params.collectionToken.transfer(
    +
            votersList[i],
    +
            shutdownVoters[_collection][votersList[i]]
    +
        );
    +
    }
    // Remove our execution flag
    delete _collectionParams[_collection];
    +
    delete votersList;
    emit CollectionShutdownCancelled(_collection);
}
```
After running the testcase on the above update, the user voters are able to get their own votes:
```bash
$ forge test --match-test test_CancelShutdownNotRefund -vv
[￿] Compiling...
[￿] Compiling 3 files with Solc 0.8.26
[￿] Solc 0.8.26 finished in 8.70s
Compiler run successful!
Ran 1 test for test/utils/CollectionShutdown.t.sol:CollectionShutdownTest
[PASS] test_CancelShutdownNotRefund() (gas: 486318)
Logs:
Address 1 balance after: 1000000000000000000
Address 2 balance after: 1000000000000000000
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 3.46s (526.80µs CPU time)
,→
Ran 1 test suite in 3.46s (3.46s CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
,→
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the shutdown voting mechanism of the CollectionShutdown contract. When a participant casts a vote to shut down a collection, the contract calls transferFrom and pulls the entire balance of the collection token that the voter holds. This operation is recorded in the _vote function, but the contract never stores any information about how many tokens were taken from each voter. Later, if the shutdown is cancelled – a path that is allowed when the quorum has been reached and the total supply condition is satisfied – the cancel function simply deletes the stored shutdown parameters and emits an event, without ever returning the tokens that were previously seized. Consequently, any user who voted and then sees the shutdown cancelled loses all of the tokens they contributed, because the contract holds them with no mechanism to refund. The root cause is the absence of a refund routine and the lack of state tracking for individual voter balances. Exploitation is straightforward: a voter participates in a shutdown vote, the quorum is met, and an authorized party calls cancel; the voter’s token balance drops to zero while the contract retains the tokens. The impact is a direct loss of funds for the voter, violating the expectation that voting does not permanently confiscate assets and breaking the accounting invariant that total token supply should remain unchanged after a cancelled shutdown. This issue manifests only when the cancel function is invoked after a successful vote, which may be rare in normal operation and therefore easy to overlook during testing. It was discovered during a security audit when a test case showed that after calling cancel, the balances of the voting addresses were zero. The problem is subtle because the cancel function appears to merely clean up state, and developers might assume that token refunds are handled elsewhere. To remediate, the contract should maintain a mapping of each voter’s deposited amount, record those amounts during voting, and iterate over the recorded voters in cancel to transfer the exact token amounts back before deleting the shutdown parameters. Adding a dedicated reclaimVote function or integrating refund logic directly into cancel would restore the lost tokens and re‑establish the intended economic guarantees of the protocol.
