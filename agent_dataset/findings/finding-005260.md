---
id: 5260
severity: "High"
---

# Commitment scheme does not prevent frontrunning

## Description

The commitment scheme used in KinoAccount9CharCommitMinter is intended to prevent frontrunning, according to the technique outlined by labelhash. However, as it is written it does not require that the commit is strictly older than the current block. Hence, a frontrunner observing the mint transaction has time to insert their own commit and frontrun.

## Proof of Concept

```solidity
KinoAccount9CharCommitMinter controls minting of the .cool top level name. Alice submits a commit to mint the name i-am-alice.cool from her address, getting her commit into a block. After a few blocks have passed (but before the 5 minute deadline) she submits a mint transaction with the following calldata:
mint(A, "i-am-alice", _initdata, "", _implementation)
Frontrunning Frank runs a frontrunning bot intended to snipe and resell names, or perhaps to cause trouble for Kinode to benefit its competitors, short its token, or any number of reasons. When he sees Alice's transaction, he immediately inserts two transactions ahead of her in the block: a commit to his own address for the name i-am-alice followed by his own mint transaction.
Frank has now successfully fronrun Alice and taken her name. As a test it might look as follows:
function testFrontRun() public {
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
    vm.prank(frank); IKinoAccountMinter(mintedTba).mint(frank, name, hex"", hex"", basicKinoAccountImpl);
    vm.expectRevert();
    vm.prank(alice); IKinoAccountMinter(mintedTba).mint(alice, name, hex"", hex"", basicKinoAccountImpl);
}
```

## Recommendation

Insert the following or similar check in the mint:
```solidity
if (_commits[_commit] >= block.timestamp) {
    revert CommitTooNew(_commit);
}
```
This would prevent Frank from frontrunning on the current block. For extra protection, you could also insist that more time has passed, e.g. 30 seconds.
```solidity
if (_commits[_commit] + 30 seconds >= block.timestamp) {
    revert CommitTooNew(_commit);
}
```
This would prevent frontrunning under boundary conditions where Alice's transaction does not have time to enter a block, but it has been seen by some participants while propagating across the network or been waiting in the mempool.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability isa front‑running weakness in the commitment‑based name‑minting contract. The contract stores a timestamp when a user submits a commit, but the mint function does not verify that the stored timestamp is strictly older than the current block. Because of this missing age check, an attacker who observes a pending mint transaction can submit his own commit for the same name and then execute a mint in the same block before the original user’s transaction is processed. The root cause is the absence of a condition such as _commits[commit] < block.timestamp (or a required delay) before allowing the mint. Exploitation proceeds by the attacker watching the mempool, creating a commit that references the same name, and then calling mint with his own address, thereby claiming the name. The victim’s mint call then reverts, resulting in loss of the name they intended to acquire and potentially loss of any ether or token paid for the mint. This occurs whenever a commit is created and the mint is called within the same block or within a short time window, because the contract treats a commit that is as recent as the current block as valid. Users who rely on the commitment scheme to protect their reservation are affected, as are the protocol’s name registry and any parties that depend on the fairness of the allocation process. The issue was discovered during a manual audit that included a proof‑of‑concept test where a simulated attacker inserted a commit and mint before the victim’s mint, causing the victim’s transaction to revert. The bug can be hard to notice because the commit appears to be recorded correctly and the contract does not emit a clear error explaining that the commit is too new; the only symptom is a failed mint. From the user’s perspective the UI shows a transaction failure, no name is assigned, and any funds sent may be lost, contrary to the expectation that the commitment guarantees exclusive rights after a short delay. The flaw violates the business logic that a commitment should create a time‑locked exclusive claim, effectively breaking the accounting assumption that once a commit is recorded the name is reserved. The recommended fix is to add a check in the mint function that the stored commit timestamp is older than the current block (or older by a configurable safety margin such as 30 seconds), and to revert with a clear error if the commit is too recent. This transforms the scheme into a proper time‑based commitment and prevents same‑block front‑running attacks.
