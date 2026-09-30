---
id: 21055
severity: "High"
---

# Queued transfers can become stuck on the source chain if new Transceivers are added or existing Transceivers are modified before completion

## Description

When a sender transfers an amount that exceeds the current outbound capacity, such transfers are sent to a queue for delayed execution within [`NttManager::_transferEntrypoint`](https://github.com/wormhole-foundation/example-native-token-transfers/blob/f4e2277b358349dbfb8a654d19a925628d48a8af/evm/src/NttManager/NttManager.sol#L306-L332). The rate limit duration is defined as an immutable variable determining the temporal lag between queueing and execution, with a typical rate limit duration being 24 hours.

```solidity
/* snip */
// now check rate limits
bool isAmountRateLimited = _isOutboundAmountRateLimited(internalAmount);
if (!shouldQueue && isAmountRateLimited) {
    revert NotEnoughCapacity(getCurrentOutboundCapacity(), amount);
}
if (shouldQueue && isAmountRateLimited) {
    // emit an event to notify the user that the transfer is rate limited
    emit OutboundTransferRateLimited(
        msg.sender, sequence, amount, getCurrentOutboundCapacity()
    );

    // queue up and return
    _enqueueOutboundTransfer(
        sequence,
        trimmedAmount,
        recipientChain,
        recipient,
        msg.sender,
        transceiverInstructions
    );

    // refund price quote back to sender
    _refundToSender(msg.value);

    // return the sequence in the queue
    return sequence;
}
/* snip */
```

In the event that new Transceivers are added or existing Transceivers are removed from the NTT Manager, any pending queued transfers within the rate limit duration can potentially revert. This is because senders might not have correctly packed the Transceiver instructions for a given Transceiver based on the new configuration, and a missing Transceiver instruction can potentially cause an array index out-of-bounds exception while calculating the delivery price when the instructions are [finally parsed](https://github.com/wormhole-foundation/example-native-token-transfers/blob/f4e2277b358349dbfb8a654d19a925628d48a8af/evm/src/NttManager/NttManager.sol#L357-L358). For example, if there are initially two Transceivers but an additional Transceiver is added while the transfer is rate-limited, the instructions array as shown below will be declared with a length of three, corresponding to the new number of enabled Transceivers; however, the transfer will have only encoded two Transceiver instructions based on the configuration at the time it was initiated.

```solidity
function parseTransceiverInstructions(
    bytes memory encoded,
    uint256 numEnabledTransceivers
) public pure returns (TransceiverInstruction[] memory) {
    uint256 offset = 0;
    uint256 instructionsLength;
    (instructionsLength, offset) = encoded.asUint8Unchecked(offset);

    // We allocate an array with the length of the number of enabled transceivers
    // This gives us the flexibility to not have to pass instructions for transceivers that
    // don't need them
    TransceiverInstruction[] memory instructions =
        new TransceiverInstruction[](numEnabledTransceivers);

    uint256 lastIndex = 0;
    for (uint256 i = 0; i < instructionsLength; i++) {
        TransceiverInstruction memory instruction;
        (instruction, offset) = parseTransceiverInstructionUnchecked(encoded, offset);

        uint8 instructionIndex = instruction.index;

        // The instructions passed in have to be strictly increasing in terms of transceiver index
        if (i != 0 && instructionIndex <= lastIndex) {
            revert UnorderedInstructions();
        }
        lastIndex = instructionIndex;

        instructions[instructionIndex] = instruction;
    }

    encoded.checkLength(offset);

    return instructions;
}
```

Missing Transceiver instructions prevents the total delivery price for the corresponding message from being calculated. This prevents any queued Transfers from being executed with the current list of transceivers. As a result, underlying sender funds will be stuck in the `NttManager` contract. Note that a similar issue occurs if the peer NTT manager contract is updated on the destination (say, after a redeployment on the source chain) before an in-flight attestation is received and executed, reverting with an invalid peer error.

## Proof of Concept

Run the following test:
```solidity
contract TestTransceiverModification is Test, INttManagerEvents, IRateLimiterEvents {
    NttManager nttManagerChain1;
    NttManager nttManagerChain2;

    using TrimmedAmountLib for uint256;
    using TrimmedAmountLib for TrimmedAmount;

    uint16 constant chainId1 = 7;
    uint16 constant chainId2 = 100;
    uint8 constant FAST_CONSISTENCY_LEVEL = 200;
    uint256 constant GAS_LIMIT = 500000;

    uint16 constant SENDING_CHAIN_ID = 1;
    uint256 constant DEVNET_GUARDIAN_PK =
        0xcfb12303a19cde580bb4dd771639b0d26bc68353645571a8cff516ab2ee113a0;
    WormholeSimulator guardian;
    uint256 initialBlockTimestamp;

    WormholeTransceiver wormholeTransceiverChain1;
    WormholeTransceiver wormholeTransceiver2Chain1;
    WormholeTransceiver wormholeTransceiver3Chain1;

    WormholeTransceiver wormholeTransceiverChain2;
    address userA = address(0x123);
    address userB = address(0x456);
    address userC = address(0x789);
    address userD = address(0xABC);

    address relayer = address(0x28D8F1Be96f97C1387e94A53e00eCcFb4E75175a);
    IWormhole wormhole = IWormhole(0x706abc4E45D419950511e474C7B9Ed348A4a716c);

    function setUp() public {
        string memory url = "https://goerli.blockpi.network/v1/rpc/public";
        vm.createSelectFork(url);
        initialBlockTimestamp = vm.getBlockTimestamp();

        guardian = new WormholeSimulator(address(wormhole), DEVNET_GUARDIAN_PK);

        vm.chainId(chainId1);
        DummyToken t1 = new DummyToken();
        NttManager implementation =
            new MockNttManagerContract(address(t1), INttManager.Mode.LOCKING, chainId1, 1 days);

        nttManagerChain1 =
            MockNttManagerContract(address(new ERC1967Proxy(address(implementation), "")));
        nttManagerChain1.initialize();

        // transceiver 1
        WormholeTransceiver wormholeTransceiverChain1Implementation = new MockWormholeTransceiverContract(
            address(nttManagerChain1),
            address(wormhole),
            address(relayer),
            address(0x0),
            FAST_CONSISTENCY_LEVEL,
            GAS_LIMIT
        );
        wormholeTransceiverChain1 = MockWormholeTransceiverContract(
            address(new ERC1967Proxy(address(wormholeTransceiverChain1Implementation), ""))
        );

        // transceiver 2
        WormholeTransceiver wormholeTransceiverChain1Implementation2 = new MockWormholeTransceiverContract(
            address(nttManagerChain1),
            address(wormhole),
            address(relayer),
            address(0x0),
            FAST_CONSISTENCY_LEVEL,
            GAS_LIMIT
        );
        wormholeTransceiver2Chain1 = MockWormholeTransceiverContract(
            address(new ERC1967Proxy(address(wormholeTransceiverChain1Implementation2), ""))
        );

        // transceiver 3
        WormholeTransceiver wormholeTransceiverChain1Implementation3 = new MockWormholeTransceiverContract(
            address(nttManagerChain1),
            address(wormhole),
            address(relayer),
            address(0x0),
            FAST_CONSISTENCY_LEVEL,
            GAS_LIMIT
        );
        wormholeTransceiver3Chain1 = MockWormholeTransceiverContract(
            address(new ERC1967Proxy(address(wormholeTransceiverChain1Implementation3), ""))
        );

        // Actually initialize properly now
        wormholeTransceiverChain1.initialize();
        wormholeTransceiver2Chain1.initialize();
        wormholeTransceiver3Chain1.initialize();

        nttManagerChain1.setTransceiver(address(wormholeTransceiverChain1));
        nttManagerChain1.setTransceiver(address(wormholeTransceiver2Chain1));

        // third transceiver is NOT set at this point for nttManagerChain1
        nttManagerChain1.setOutboundLimit(type(uint64).max);
        nttManagerChain1.setInboundLimit(type(uint64).max, chainId2);

        // Chain 2 setup
        vm.chainId(chainId2);
        DummyToken t2 = new DummyTokenMintAndBurn();
        NttManager implementationChain2 =
            new MockNttManagerContract(address(t2), INttManager.Mode.BURNING, chainId2, 1 days);

        nttManagerChain2 =
            MockNttManagerContract(address(new ERC1967Proxy(address(implementationChain2), "")));
        nttManagerChain2.initialize();

        WormholeTransceiver wormholeTransceiverChain2Implementation = new MockWormholeTransceiverContract(
            address(nttManagerChain2),
            address(wormhole),
            address(relayer),
            address(0x0),
            FAST_CONSISTENCY_LEVEL,
            GAS_LIMIT
        );

        wormholeTransceiverChain2 = MockWormholeTransceiverContract(
            address(new ERC1967Proxy(address(wormholeTransceiverChain2Implementation), ""))
        );
        wormholeTransceiverChain2.initialize();

        nttManagerChain2.setTransceiver(address(wormholeTransceiverChain2));
        nttManagerChain2.setOutboundLimit(type(uint64).max);
        nttManagerChain2.setInboundLimit(type(uint64).max, chainId1);

        // Register peer contracts for the nttManager and transceiver. Transceivers and nttManager each have the concept of peers here.
        nttManagerChain1.setPeer(chainId2, bytes32(uint256(uint160(address(nttManagerChain2)))), 9);
        nttManagerChain2.setPeer(chainId1, bytes32(uint256(uint160(address(nttManagerChain1)))), 7);

        // Set peers for the transceivers
        wormholeTransceiverChain1.setWormholePeer(
            chainId2, bytes32(uint256(uint160(address(wormholeTransceiverChain2))))
        );

       wormholeTransceiver2Chain1.setWormholePeer(
            chainId2, bytes32(uint256(uint160(address(wormholeTransceiverChain2))))
        );

       wormholeTransceiver3Chain1.setWormholePeer(
            chainId2, bytes32(uint256(uint160(address(wormholeTransceiverChain2))))
        );

        wormholeTransceiverChain2.setWormholePeer(
            chainId1, bytes32(uint256(uint160(address(wormholeTransceiverChain1))))
        );

        require(nttManagerChain1.getThreshold() != 0, "Threshold is zero with active transceivers");

        // Actually set it
        nttManagerChain1.setThreshold(2);
        nttManagerChain2.setThreshold(1);
    }

    function testTransceiverModification() external {
        vm.chainId(chainId1);

        // Setting up the transfer
        DummyToken token1 = DummyToken(nttManagerChain1.token());
        uint8 decimals = token1.decimals();

        token1.mintDummy(address(userA), 5 * 10 ** decimals);
        uint256 outboundLimit = 4 * 10 ** decimals;
        nttManagerChain1.setOutboundLimit(outboundLimit);

        vm.startPrank(userA);

        uint256 transferAmount = 5 * 10 ** decimals;
        token1.approve(address(nttManagerChain1), transferAmount);

        // transfer with shouldQueue == true
        uint64 qSeq = nttManagerChain1.transfer(
            transferAmount, chainId2, toWormholeFormat(userB), true, encodeTransceiverInstructions(true)
        );
        vm.stopPrank();

        assertEq(qSeq, 0);
        IRateLimiter.OutboundQueuedTransfer memory qt = nttManagerChain1.getOutboundQueuedTransfer(0);
        assertEq(qt.amount.getAmount(), transferAmount.trim(decimals, decimals).getAmount());
        assertEq(qt.recipientChain, chainId2);
        assertEq(qt.recipient, toWormholeFormat(userB));
        assertEq(qt.txTimestamp, initialBlockTimestamp);

        // assert that the contract also locked funds from the user
        assertEq(token1.balanceOf(address(userA)), 0);
        assertEq(token1.balanceOf(address(nttManagerChain1)), transferAmount);

        // elapse some random time - 60 seconds
        uint256 durationElapsedTime = initialBlockTimestamp + 60;

        // now add a third transceiver
        nttManagerChain1.setTransceiver(address(wormholeTransceiver3Chain1));

        // verify that the third transceiver is added
        assertEq(nttManagerChain1.getTransceivers().length, 3);

        // remove second transceiver
        nttManagerChain1.removeTransceiver(address(wormholeTransceiver2Chain1));

          // verify that the second transceiver is removed
        assertEq(nttManagerChain1.getTransceivers().length, 2);

         // elapse rate limit duration
         durationElapsedTime = initialBlockTimestamp + nttManagerChain1.rateLimitDuration();

        vm.warp(durationElapsedTime);

        vm.expectRevert(stdError.indexOOBError); //index out of bounds - transceiver instructions array does not have a third element to access
        nttManagerChain1.completeOutboundQueuedTransfer(0);
    }

    // Encode an instruction for each of the relayers
    function encodeTransceiverInstructions(bool relayer_off) public view returns (bytes memory) {
        WormholeTransceiver.WormholeTransceiverInstruction memory instruction =
            IWormholeTransceiver.WormholeTransceiverInstruction(relayer_off);

        bytes memory encodedInstructionWormhole =
            wormholeTransceiverChain1.encodeWormholeTransceiverInstruction(instruction);

        TransceiverStructs.TransceiverInstruction memory TransceiverInstruction1 =
        TransceiverStructs.TransceiverInstruction({index: 0, payload: encodedInstructionWormhole});
        TransceiverStructs.TransceiverInstruction memory TransceiverInstruction2 =
        TransceiverStructs.TransceiverInstruction({index: 1, payload: encodedInstructionWormhole});

        TransceiverStructs.TransceiverInstruction[] memory TransceiverInstructions =
            new TransceiverStructs.TransceiverInstruction[](2);

        TransceiverInstructions[0] = TransceiverInstruction1;
        TransceiverInstructions[1] = TransceiverInstruction2;

        return TransceiverStructs.encodeTransceiverInstructions(TransceiverInstructions);
    }
}
```

## Recommendation

Consider passing no instructions into the delivery price estimation when the Transceiver index does not exist.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns delayed outbound transfers that are placed in a queue when the requested amount exceeds the current outbound capacity of the NTT manager. The contract records the transfer together with a set of transceiver instructions that are encoded according to the list of enabled transceivers at the moment of queuing. Because the rate‑limit duration (typically 24 hours) postpones execution, the configuration of the NTT manager can be altered – new transceivers may be added or existing ones removed – before the queued transfer is finally processed. When the manager later attempts to parse the stored instructions, it allocates an array whose length matches the *current* number of enabled transceivers. If the stored payload contains fewer instructions than the new array length, the parsing loop writes to an index that does not exist, triggering an out‑of‑bounds revert. Consequently the queued transfer cannot be completed, the delivery price cannot be calculated, and the funds that were locked in the NTT manager remain permanently stuck. The issue is discovered during a formal audit by reproducing the scenario in a test that adds a third transceiver after queuing a transfer that only contains two instructions, then removes one of the original transceivers and finally attempts to complete the transfer, which reverts with an index‑out‑of‑bounds error. The bug is subtle because it only manifests after a time delay and only when the contract’s transceiver set changes, making it easy to miss during normal functional testing. Users experience the problem as a transfer that appears to be queued successfully, but later the transaction fails and their token balance in the NTT manager stays reduced while their external balance shows zero, effectively “funds disappear”. The affected parties are the senders of the queued transfers, any downstream protocol that relies on timely cross‑chain delivery, and the overall trustworthiness of the bridge. The root cause is a mismatch between the snapshot of transceiver configuration stored at queuing time and the live configuration used at execution time. To remediate, the contract should either store a snapshot of the transceiver list with each queued transfer, validate that the number of provided instructions matches the current configuration before queuing, or modify the price‑estimation routine to safely handle missing instructions (for example by treating absent indices as zero‑cost placeholders). This prevents the out‑of‑bounds access and ensures that queued funds can always be released, preserving accounting integrity and user expectations that a queued transfer will eventually be executed or refunded.
