---
id: 21054
severity: "High"
---

# Queued transfers can become stuck on the source chain if Transceiver instructions are encoded in the incorrect order

## Description

** In the case of multiple Transceivers, the current logic expects that a sender encodes Transceiver instructions in order of increasing Transceiver registration index, as validated in [`TransceiverStructs::parseTransceiverInstructions`](https://github.com/wormhole-foundation/example-native-token-transfers/blob/f4e2277b358349dbfb8a654d19a925628d48a8af/evm/src/libraries/TransceiverStructs.sol#L326-L359). Under normal circumstances, this logic works as expected, and the transaction fails when the user packs transceiver instructions in the incorrect order.
```solidity
/* snip */
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
/* snip */
```
However, this requirement on the order of Transceiver indices is not checked when transfers are initially queued for delayed execution. As a result, a transaction where this is the case will fail when the user calls `NttManager::completeOutboundQueuedTransfer` to execute a queued transfer.
** The sender's funds are transferred to the NTT Manager when messages are queued. However, this queued message can never be executed if the Transceiver indices are incorrectly ordered and, as a result, the user funds remain stuck in the NTT Manager.

## Proof of Concept

** Run the following test:
```solidity
contract TestWrongTransceiverOrder is Test, INttManagerEvents, IRateLimiterEvents {
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

        // Actually initialize properly now
        wormholeTransceiverChain1.initialize();
        wormholeTransceiver2Chain1.initialize();

        nttManagerChain1.setTransceiver(address(wormholeTransceiverChain1));
        nttManagerChain1.setTransceiver(address(wormholeTransceiver2Chain1));
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

        wormholeTransceiverChain2.setWormholePeer(
            chainId1, bytes32(uint256(uint160(address(wormholeTransceiverChain1))))
        );

        require(nttManagerChain1.getThreshold() != 0, "Threshold is zero with active transceivers");

        // Actually set it
        nttManagerChain1.setThreshold(2);
        nttManagerChain2.setThreshold(1);
    }

    function testWrongTransceiverOrder() external {
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
            transferAmount, chainId2, toWormholeFormat(userB), true, encodeTransceiverInstructionsJumbled(true)
        );

        assertEq(qSeq, 0);
        IRateLimiter.OutboundQueuedTransfer memory qt = nttManagerChain1.getOutboundQueuedTransfer(0);
        assertEq(qt.amount.getAmount(), transferAmount.trim(decimals, decimals).getAmount());
        assertEq(qt.recipientChain, chainId2);
        assertEq(qt.recipient, toWormholeFormat(userB));
        assertEq(qt.txTimestamp, initialBlockTimestamp);

        // assert that the contract also locked funds from the user
        assertEq(token1.balanceOf(address(userA)), 0);
        assertEq(token1.balanceOf(address(nttManagerChain1)), transferAmount);

         // elapse rate limit duration - 1
        uint256 durationElapsedTime = initialBlockTimestamp + nttManagerChain1.rateLimitDuration();

        vm.warp(durationElapsedTime);

        vm.expectRevert(0x71f23ef2); //UnorderedInstructions() selector
        nttManagerChain1.completeOutboundQueuedTransfer(0);
    }

    // Encode an instruction for each of the relayers
    function encodeTransceiverInstructionsJumbled(bool relayer_off) public view returns (bytes memory) {
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

        TransceiverInstructions[0] = TransceiverInstruction2;
        TransceiverInstructions[1] = TransceiverInstruction1;

        return TransceiverStructs.encodeTransceiverInstructions(TransceiverInstructions);
    }
}
```

## Recommendation

** When the transfer amount exceeds the current outbound capacity, verify the Transceiver instructions are ordered correctly before adding a message to the list of queued transfers.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the handling of queued outbound token transfers in the NTT Manager when multiple transceivers are used. The contract expects the list of transceiver instructions supplied by the sender to be sorted in strictly increasing order of their registration index. This ordering is enforced by the parsing routine that iterates over the encoded instructions during the execution of a queued transfer; if an instruction index is not greater than the previous one the routine reverts with UnorderedInstructions. However, the same ordering check is omitted when the transfer is initially queued for delayed execution. Consequently, a user can submit a transfer that passes the initial queuing step – the manager locks the user's tokens and records the transfer – but later, when the queued transfer is processed by calling completeOutboundQueuedTransfer, the parsing routine detects the out‑of‑order indices and aborts. The abort leaves the locked tokens permanently held by the NTT Manager because there is no fallback path to release them. The root cause is the missing validation of instruction ordering at the point where the transfer is added to the outbound queue, combined with the assumption that the queued data will always be well‑formed. An attacker (or a careless user) can exploit this by deliberately encoding the transceiver instructions in a jumbled order, for example by swapping the positions of two instructions. When the outbound capacity limit forces the transfer to be queued, the transaction succeeds, the user’s balance becomes zero, and the contract’s token balance increases, giving the impression that the transfer is in progress. Later, the completion step fails with a revert, and the funds remain inaccessible, effectively creating a denial‑of‑service condition for the affected user and reducing the overall liquidity of the protocol. This issue manifests only when the outbound limit is exceeded (triggering queuing) and when more than one transceiver is configured, making it easy to miss during casual testing because the initial transfer does not revert. It was discovered during a formal audit by Cyfrin, which reproduced the failure with a unit test that intentionally encoded the instructions in reverse order and observed the revert on completion. The problem is subtle because the contract does not emit a clear error at the queuing stage, and the user sees no immediate indication that the transfer will later fail. To remediate, the manager should verify that the transceiver instruction list is correctly ordered before adding a transfer to the outbound queue, or enforce ordering at the encoding layer, thereby preventing malformed queued messages from ever being stored. This class of bug falls under “incorrect input validation for delayed execution paths” and can lead to funds being locked, refunds not being delivered, and accounting inconsistencies within cross‑chain token bridges.
