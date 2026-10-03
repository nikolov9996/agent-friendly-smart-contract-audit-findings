---
id: 25007
severity: "Medium"
---

# Inconsistent sequencer unexpected delay in DelayBuffer may harm users calling forceInclusion()

## Description



## Proof of Concept

When the sequencer is down, users may call `SequencerInbox::forceInclusion()` to get their message added to the inbox `sequencerInboxAccs`. However, there is an incosistency when the sequencer has been down and there is more than 1 message, or even if just 1 message.

The `DelayBuffer` is used to dynamically adjust how much delay a user has to wait to call `SequencerInbox::forceInclusion()`. The buffer increase mechanism is not relevant for this issue.

The buffer decrease consists of subtracting the last time the buffer was updated, `self.prevSequencedBlockNumber`, by the previous block number of the last delay buffer update, `self.prevBlockNumber`. This is done this way to ensure that the sequencer delay can not be double counted, as the delayed inbox may have more than 1 delayed message.

However, the approach taken as a way of protecting the sequencer and not depleting the buffer incorrectly as the drawback that it also means that the buffer will not always be decreased.

For example, if the sequencer is working at a block number A, a message is submited at block number A + 10 and another one at block number A + 110. If the sequencer is down, the user has to wait, for example, delay blocks of 100 (or the delay buffer, depending on the [smallest](<https://github.com/code-423n4/2024-05-arbitrum-foundation/blob/main/src/bridge/SequencerInbox.sol#L843-L845>)). If 200 blocks have passed since A + 10 (the first message), both delayed messages may be force included, at block number A + 210.

The discrepancy is that, depending on how the delayed messages are included, the buffer delay will be reduced differently. If both messages are removed at once, by calling `SequencerInbox::forceInclusion()` with the id of the newest message, the buffer delay will not be decreased, as `self.prevBlockNumber` is A, the same as `self.prevSequencedBlockNumber`. This would harm users that want to force included messages as the buffer would be bigger and they would have to wait more time for their message to be force included.

If the oldest message is first force included, the buffer delay will not decreased, as above, but `self.prevSequencedBlockNumber` will be updated to A + 210 and `self.prevBlockNumber` to A + 10. Then, if the second message is force included, `self.prevSequencedBlockNumber - self.prevBlockNumber == A + 210 - (A + 10) == 200`, which means that the buffer would correctly decrease as the sequencer was offline (ignoring the fact that there is a threshold, but the issue is the same as long as the delay is bigger than the threshold).

As a proof of concept, add the following test to `SequencerInbox.t.sol`. It shows that given 2 messages, the delay buffer is only decreased if the first message is forcely included first and only after is the newest message included. If the given `delayedMessagesRead` is the if of the second message, without forcely including the first one first, the buffer will not decrease.

```
function test_POC_InconsistentBuffer_Decrease() public {
    BufferConfig memory configBufferable = BufferConfig({
        threshold: 600, //60 * 60 * 2 / 12
        max: 14400, //24 * 60 * 60 / 12 * 2
        replenishRateInBasis: 714
    });

    (SequencerInbox seqInbox, Bridge bridge) = deployRollup(false, true, configBufferable);
    address delayedInboxSender = address(140);
    uint8 delayedInboxKind = 3;
    bytes32 messageDataHash = RAND.Bytes32();

    (uint64 bufferBlocks, ,,,,) = seqInbox.buffer();
    assertEq(bufferBlocks, 14400);

    vm.startPrank(dummyInbox);
    bridge.enqueueDelayedMessage(delayedInboxKind, delayedInboxSender, messageDataHash);
    vm.roll(block.number + 1100);
    bridge.enqueueDelayedMessage(delayedInboxKind, delayedInboxSender, messageDataHash);
    vm.stopPrank();

    vm.roll(block.number + 500);

    uint256 delayedMessagesRead = bridge.delayedMessageCount();

    // buffer is not decreased if the first and second messages are included at once
    seqInbox.forceInclusion(
            delayedMessagesRead,
            delayedInboxKind,
            [uint64(block.number - 500), uint64(block.timestamp)],
            0,
            delayedInboxSender,
            messageDataHash
        );
    (bufferBlocks, ,,,,) = seqInbox.buffer();
    assertEq(bufferBlocks, 14400);

    // buffer is only decreased if the first message is included first
    /*seqInbox.forceInclusion(
            delayedMessagesRead - 6,
            delayedInboxKind,
            [uint64(block.number - 1600), uint64(block.timestamp)],
            0,
            delayedInboxSender,
            messageDataHash
    );
    (bufferBlocks, ,,,,) = seqInbox.buffer();
    assertEq(bufferBlocks, 14400);

    seqInbox.forceInclusion(
            delayedMessagesRead,
            delayedInboxKind,
            [uint64(block.number - 500), uint64(block.timestamp)],
            0,
            delayedInboxSender,
            messageDataHash
        );
    (bufferBlocks, ,,,,) = seqInbox.buffer();
    assertEq(bufferBlocks, 13478);*/
}
```

## Recommendation

A mitigation must be carefully taken as not to introduce double accounting of the buffer delay. One solution that would fix this issue is tracking the total unexpected delay separately and making it equal to the `block.number` minus the maximum between the previous sequenced block number and the oldest delayed message that was not yet included. This way, by doing the maximum with the last sequenced, we guarantee that no double accounting of delays takes place. By doing the maximum with the oldest delayed message, we guarantee that the delay is real and not that no message was submitted.
