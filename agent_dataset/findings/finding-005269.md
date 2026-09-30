---
id: 5269
severity: "High"
---

# Fixed commitment scheme has incorrect time bounds check, so remains ineffective

## Description

A fix has been submitted for the issue "Commitment scheme does not prevent frontrunning", but it does not mitigate the issue. The proof of concept is still valid. The problem is the timing check:
```solidity
// if the commit is less than MIN_COMMIT_AGE old, it's too new
if (commitExpiration - maxCommitAge >= block.timestamp + minCommitAge) {
    revert CommitTooNew();
}
```
Note that commitExpiration - maxCommitAge gives the timestamp at which the commit was submitted.
This will always be larger or equal to the current timestamp, so commitExpiration - maxCommitAge >= block.timestamp will always yield true, so of course commitExpiration - maxCommitAge >= block.timestamp + minCommitAge will also always yield true. The minCommitAge term should be on the other side of the inequality.

## Proof of Concept

KinoAccount9CharCommitMinter controls minting of the .cool top level name. Alice submits a commit to mint the name i-am-alice.cool from her address, getting her commit into a block. After a few blocks have passed (but before the 5 minute deadline) she submits a mint transaction with the following calldata:
mint(A, "i-am-alice", _initdata, "", _implementation)
Frontrunning Frank runs a frontrunning bot intended to snipe and resell names, or perhaps to cause trouble for Kinode to benefit its competitors, short its token, or any number of reasons. When he sees Alice's transaction, he immediately inserts two transactions ahead of her in the block: a commit to his own address for the name i-am-alice followed by his own mint transaction.
Frank has now successfully frontrun Alice and taken her name. As a test it might look as follows:
```solidity
function testFrontRun2() public {
    bytes memory name = "i-am-alice";
    address alice = address(42);
    address frank = address(1337);
    bytes32 alice_commit = IKinoAccountCommittable(address(mintedTba)).getCommitHash(name, alice);
    vm.prank(alice); IKinoAccountCommittable(address(mintedTba)).commit(alice_commit);
    vm.warp(block.timestamp + 1 minutes);
    // At this point, the mint transaction from Alice is in the mempool.
    // Frank can see it, and create his own transactions based on the the name, which is present in Alice's calldata.
    bytes32 frank_commit = IKinoAccountCommittable(address(mintedTba)).getCommitHash(name, frank);
    vm.prank(frank); IKinoAccountCommittable(address(mintedTba)).commit(frank_commit);
    vm.expectRevert();
    vm.prank(frank); IKinoAccountMinter(mintedTba).mint(frank, name, hex"", basicKinoAccountImpl);
    vm.prank(alice); IKinoAccountMinter(mintedTba).mint(alice, name, hex"", basicKinoAccountImpl);
}
```
This test would fail currently, because Frank's mint would not revert as expected.

## Recommendation

Change the check for too recent commits to read as follows (note the moved minCommitAge term):
```solidity
// if the commit is less than MIN_COMMIT_AGE old, it's too new
if (commitExpiration - maxCommitAge + minCommitAge >= block.timestamp) {
    revert CommitTooNew();
}
```
Also add the above proof-of-concept to the test suite.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in a commitment‑based name‑minting contract where the logic that enforces a minimum age for a commit is written incorrectly. The contract stores a timestamp derived from commitExpiration minus maxCommitAge, which represents the moment the commit was recorded. To prevent front‑running, the code is supposed to reject a mint request if the commit is younger than a configured MIN_COMMIT_AGE. The implemented condition compares this stored timestamp against the current block timestamp plus the minimum age using the expression (commitExpiration - maxCommitAge >= block.timestamp + minCommitAge). Because the left‑hand side is always greater than or equal to block.timestamp, the inequality is true for every possible block, meaning the check either always triggers a revert or never enforces the intended delay, depending on how the surrounding logic interprets the result. In practice the check becomes ineffective, allowing an attacker to submit a competing commit and mint the same name in the same block after the victim’s commit has been observed. The exploit works as follows: a user submits a commit for a name, the transaction is included in a block, and before the user’s later mint transaction is mined, a malicious actor observes the pending mint, inserts his own commit and mint transactions ahead of the user’s transaction, and successfully claims the name because the contract does not correctly verify that the original commit is old enough. From the user’s perspective the expected outcome – receiving ownership of the chosen name after the waiting period – is violated; instead the transaction either reverts unexpectedly or the name is taken by the attacker, resulting in a loss of the desired asset and possibly the associated value. The issue was discovered during a security audit when the original fix for a known front‑running problem was examined and the timing check was found to be mathematically flawed. The bug is subtle because the condition compiles without error and appears to perform a sensible comparison, yet the placement of the MIN_COMMIT_AGE term on the wrong side of the inequality defeats the security guarantee. The class of bug is an incorrect boundary check in a time‑based commitment scheme, a common pattern where off‑by‑one or reversed inequality errors render age constraints ineffective. To remediate the problem the comparison must be rewritten so that the minimum age is added to the stored commit timestamp before being compared to the current time, for example (commitExpiration - maxCommitAge + minCommitAge >= block.timestamp). Adding comprehensive tests that replicate the front‑running scenario ensures the fix is verified.
