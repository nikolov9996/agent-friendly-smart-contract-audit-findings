---
id: 4578
severity: "High"
---

# Inverted Merkle Proof Veriﬁcation in claimLogic Submitted by Luck, also found by MukulKolpe, j0xbear, Shubham, thisvishalsingh, sohrabhind, shealtielanz, 0xTheBlackPanther, VAD37, chrissavov, ilyadruzh, pineneedles, 0x37, magicCentaur, SpDream, 0xAura, SpDream, BengalCatBalu, krishnambstu, limesss, Agontuk1, JesJupyter, Timepunk, aksoy, Aslanbek Aibimov, mmvds, ZoA, merulz99, TamayoNft, chainsentry and newspacexyz

## Description

When verifying a Merkle proof, the contract leverages OpenZeppelin's MerkleProof.verify, which returns true if and only if a leaf can be proved to be part of the Merkle tree defined by root.
According to OpenZeppelin's MerkleProof:
```solidity
/**
 * @dev Returns true if a leaf can be proved to be a part of a Merkle tree
 * defined by root. For this, a proof must be provided, containing
 * sibling hashes on the branch from the leaf to the root of the tree. Each
 * pair of leaves and each pair of pre-images are assumed to be sorted.
 *
 * This version handles proofs in memory with a custom hashing function.
 */
function verify(
    bytes32[] memory proof,
    bytes32 root,
    bytes32 leaf,
    function(bytes32, bytes32) view returns (bytes32) hasher
) internal view returns (bool) {
    return processProof(proof, leaf, hasher) == root;
}
```
In the vulnerable claimLogic(...) function, however, the code uses require(!_verify(...)), thus negating the result of MerkleProof.verify. Speciﬁcally:
```solidity
function claimLogic(
    EpochDistributorStorage storage $e,
    DefiAppHomeCenterStorage storage $,
    uint256 epoch,
    MerkleUserDistroInput memory distro,
    bytes32[] calldata distroProof,
    bool withStaking
) public {
    require($e.isClaimed[epoch][distro.userId] == false, EpochDistributor_epochAlreadyDistributed());
    // The bug: uses `!_verify(...)` instead of `_verify(...)`
    require(
        !_verify(distroProof, $e.distributionMerkleRoots[epoch], getLeaveUserDistroTree(distro)),
        EpochDistributor_invalidDistroProof()
    );
    address receiver = $e.userConfigs[distro.userId].receiver;
    if (!withStaking) Home($.homeToken).safeTransfer(receiver, distro.tokens);
    $e.isClaimed[epoch][distro.userId] = true;
    emit DefiAppHomeCenter.Claimed(epoch, distro.userId, receiver, distro.tokens);
}
```
```solidity
function _verify(bytes32[] calldata proof, bytes32 root, bytes32 leaf) private pure returns (bool) {
    return MerkleProof.verify(proof, root, leaf);
}
```
• Valid proof returns true → !true = false → require(false, ...) → revert.
• Invalid proof returns false → !false = true → passes the require.
Hence, legitimate claimants with correct proofs are blocked, while incorrect proofs are accepted.

Impact Explanation:
1. Legitimate claimants holding valid proofs are entirely blocked from claiming their tokens. This effectively deprives them of their rightful assets, as the contract reverts on any valid proof.
2. Attackers presenting an invalid proof can successfully pass the inverted check. Although they may not directly mint tokens from thin air, they can fraudulently mark themselves as having claimed, which can disrupt or deny actual legitimate claimants later. In scenarios where the contract itself directly transfers tokens upon claim, a malicious actor could receive tokens they're not entitled to, thus causing asset losses for the intended legitimate recipients.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;
import "forge-std/Test.sol";

/**
 * @notice A minimal PoC demonstrating the inverted Merkle-proof check:
 * using `require(! _verify(...))` instead of `require(_verify(...))`.
 * This version ensures function arguments use `memory` so that we
 * can pass memory variables from the same test contract.
 */
contract EpochDistributorPoC is Test {
    /// @dev Simulated mapping: whether a user has claimed in a given epoch.
    mapping(uint256 => mapping(address => bool)) public isClaimed;

    /// @dev Simulated distribution Merkle root for each epoch.
    mapping(uint256 => bytes32) public distributionMerkleRoots;

    /**
     * @dev A simplified struct for demonstration. In real code, you'd have more fields
     * or different hashing logic for forming the leaf from (tokens, user, etc.).
     */
    struct MerkleUserDistroInput {
        uint256 tokens;
        address userId;
    }

    /**
     * @dev A mock verify function. In real usage, you'd do:
     * bool isValid = MerkleProof.verify(proof, root, leaf);
     * Here, `pretendValid` is just a bool to simulate "true = valid proof".
     */
    function _verify(
        bytes32[] memory proof,
        bytes32 root,
        bytes32 leaf,
        bool pretendValid
    ) public pure returns (bool) {
        return pretendValid;
    }

    /**
     * @dev Returns a simplified leaf by hashing (tokens, userId).
     */
    function getLeaf(MerkleUserDistroInput memory distro) public pure returns (bytes32) {
        return keccak256(abi.encode(distro.tokens, distro.userId));
    }

    /**
     * @dev The bugged logic: using `require(! _verify(...))`.
     * If _verify returns true => !true == false => require(false) => revert
     * If _verify returns false => !false == true => require(true) => passes
     */
    function claimLogicWrong(
        uint256 epoch,
        MerkleUserDistroInput memory distro,
        bytes32[] memory distroProof,
        bool pretendValid
    ) public {
        require(!isClaimed[epoch][distro.userId], "Already claimed!");
        // Bug: we invert the verify result with `!_verify(...)`
        require(
            !_verify(distroProof, distributionMerkleRoots[epoch], getLeaf(distro), pretendValid),
            "Invalid proof!"
        );
        isClaimed[epoch][distro.userId] = true;
    }

    // =========== TESTS ===========

    /**
     * @dev Demonstrates that when the proof is actually invalid (pretendValid = false),
     * it ironically succeeds because require(!false) => require(true) => no revert.
     */
    function testWrongLogic_invalidProofPasses() public {
        uint256 epoch = 2;
        distributionMerkleRoots[epoch] = bytes32(uint256(5678));
        MerkleUserDistroInput memory distro = MerkleUserDistroInput({
            tokens: 200,
            userId: address(this)
        });
        bytes32[] memory emptyProof = new bytes32[](0);
        // pretendValid = false => _verify == false => !false => true => pass
        claimLogicWrong(epoch, distro, emptyProof, false);
        // Check that the user is incorrectly marked as claimed
        assertTrue(isClaimed[epoch][address(this)], "Should claim with invalid proof in the buggy logic!");
    }

    /**
     * @dev Demonstrates that when the proof is actually valid (pretendValid = true),
     * it fails because require(!true) => require(false) => revert.
     */
    function testWrongLogic_validProofFails() public {
        uint256 epoch = 1;
        distributionMerkleRoots[epoch] = bytes32(uint256(1234)); // mock root for example
        MerkleUserDistroInput memory distro = MerkleUserDistroInput({
            tokens: 100,
            userId: address(this)
        });
        bytes32[] memory emptyProof = new bytes32[](0);
        // pretendValid = true => _verify == true => !true => false => revert
        vm.expectRevert(bytes("Invalid proof!"));
        claimLogicWrong(epoch, distro, emptyProof, true);
        // Check that the user isn't marked as claimed
        assertFalse(isClaimed[epoch][address(this)], "Should NOT claim with correct proof in the buggy logic!");
    }
}
```
Output:
Ran 2 tests for test/Counter.t.sol:EpochDistributorPoC
[PASS] testWrongLogic_invalidProofPasses() (gas: 48910)
Traces:
[48910] EpochDistributorPoC::testWrongLogic_invalidProofPasses()
[0] VM::assertTrue(true, "Should claim with invalid proof in the buggy logic!") [staticcall]
←[Return]
←[Stop]
[PASS] testWrongLogic_validProofFails() (gas: 28428)
Traces:
[28428] EpochDistributorPoC::testWrongLogic_validProofFails()
[0] VM::expectRevert(custom error 0xf28dceb3: Invalid proof!)
←[Return]
←[Revert] revert: Invalid proof!
Suite result: ok. 2 passed; 0 failed; 0 skipped; finished in 4.88ms (2.70ms CPU time)

## Recommendation

Replace the inverted check:
```solidity
require(
    !_verify(distroProof, $e.distributionMerkleRoots[epoch], getLeaveUserDistroTree(distro)),
    EpochDistributor_invalidDistroProof()
);
```
with the correct logic:
```solidity
require(
    _verify(distroProof, $e.distributionMerkleRoots[epoch], getLeaveUserDistroTree(distro)),
    EpochDistributor_invalidDistroProof()
);
```
By removing the negation, valid proofs (_verify == true) will pass, invalid proofs (_verify == false) will revert, restoring the intended Merkle proof security.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an inverted Merkle‑proof verification in the claimLogic function of the epoch distributor contract. The function calls OpenZeppelin's MerkleProof.verify, which returns true when a leaf is correctly proved against the stored Merkle root. However the result is negated with a logical NOT inside a require statement, so the require condition becomes true only when the verification returns false. Consequently a valid proof causes the require to fail and the transaction reverts, while an invalid proof satisfies the require and allows the function to continue. This logic error blocks legitimate claimants from receiving their allocated tokens and permits an attacker to submit a bogus proof, mark the claim as completed, and potentially receive tokens that should belong to the rightful recipient. The bug manifests whenever a user calls claimLogic with any Merkle proof, regardless of its correctness, and it affects all participants of the distribution, including token holders and the protocol that relies on accurate accounting of claimed amounts. The issue was discovered during a manual audit when reviewers noticed the unexpected negation in the require statement. It can be hard to spot because the verify function returns a boolean and the surrounding code appears syntactically correct; only a careful review of the logical condition reveals the inversion. From a user perspective the UI may show a transaction reverting with an 'Invalid proof' error even though the proof was generated from the official root, or it may show that the claim is recorded as completed without any token transfer, leading to missing balances and confusion. The vulnerability belongs to the class of logical inversion bugs where a security check is applied with the opposite polarity, breaking the intended access control or accounting rule. To remediate the issue the require should be written without the NOT operator, i.e., require(_verify(...), ...) so that a true verification passes and a false verification reverts, restoring the intended Merkle‑proof protection.
