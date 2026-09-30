---
id: 20461
severity: "High"
---

# QVSimpleStrategy never updates

## Description

QVSimpleStrategy._allocate calls _hasVoiceCreditsLeft to check that the recipient has voice credits left to allocate
https://github.com/allo-protocol/allo-v2/blob/main/allo-v2/contracts/strategies/qv-simple/QVSimpleStrategy.sol#L121
```solidity
function _allocate(bytes memory _data, address _sender) internal virtual override {
    // check that the recipient has voice credits left to allocate
    if (!_hasVoiceCreditsLeft(voiceCreditsToAllocate, allocator.voiceCredits)) revert INVALID();
    _qv_allocate(allocator, recipient, recipientId, voiceCreditsToAllocate, _sender);
}
```
QVSimpleStrategy._hasVoiceCreditsLeft checks _voiceCreditsToAllocate + _allocatedVoiceCredits <= maxVoiceCreditsPerAllocator
https://github.com/allo-protocol/allo-v2/blob/main/allo-v2/contracts/strategies/qv-simple/QVSimpleStrategy.sol#L144
```solidity
function _hasVoiceCreditsLeft(uint256 _voiceCreditsToAllocate, uint256 _allocatedVoiceCredits)
    internal
    view
    override
    returns (bool)
{
    return _voiceCreditsToAllocate + _allocatedVoiceCredits <= maxVoiceCreditsPerAllocator;
}
```
The problem is that allocator.voiceCredits is always zero. Both QVSimpleStrategy and QVBaseStrategy don't update allocator.voiceCredits. Thus, allocators can cast more votes than maxVoiceCreditsPerAllocator.
Every allocator has an unlimited number of votes.

## Proof of Concept

no poc

## Recommendation

Updates allocator.voiceCredits in QVSimpleStrategy._allocate.
```solidity
function _allocate(bytes memory _data, address _sender) internal virtual override {
    ...
    // check that the recipient has voice credits left to allocate
    if (!_hasVoiceCreditsLeft(voiceCreditsToAllocate, allocator.voiceCredits)) revert INVALID();
    allocator.voiceCredits += voiceCreditsToAllocate;
    _qv_allocate(allocator, recipient, recipientId, voiceCreditsToAllocate, _sender);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the quadratic voting (QV) strategy implementation where the contract fails to keep an accurate record of the voice credits that each allocator has already spent. When an allocator calls the internal _allocate function, the code checks whether the allocator still has voice credits left by invoking _hasVoiceCreditsLeft, which compares the sum of the requested credits and the allocator's stored voiceCredits against the protocol‑defined maxVoiceCreditsPerAllocator. However, the allocator.voiceCredits field is never updated after a successful allocation because both QVSimpleStrategy and its base contract omit any state mutation for this variable. As a result, allocator.voiceCredits remains permanently zero, causing the condition _voiceCreditsToAllocate + 0 <= maxVoiceCreditsPerAllocator to be true for any amount of credits that does not exceed the maximum in a single call, and, more importantly, the check can be bypassed repeatedly across multiple calls. An attacker who controls an allocator can therefore allocate an unlimited number of voice credits, casting far more votes than the protocol intends. This breaks the fundamental accounting assumption of quadratic voting that each participant’s influence is bounded by a fixed credit pool, allowing the attacker to skew voting outcomes, manipulate fund distribution, or otherwise compromise the fairness of the protocol. The issue manifests whenever the _allocate function is executed, which is the normal path for any legitimate vote allocation, making it difficult to detect because the contract does not emit any warning or revert when the credit limit is exceeded; the logic appears to enforce the limit but silently ignores the actual usage. The bug was discovered during a systematic audit that examined state updates and identified that the allocator’s voiceCredits field was never written to. To remediate the problem, the contract should increment allocator.voiceCredits by the amount of credits allocated before invoking the voting logic, thereby ensuring that subsequent allocations correctly reflect the remaining credit balance and that the invariant enforced by _hasVoiceCreditsLeft holds across calls. In abstract terms, this is a classic missing‑state‑update or accounting‑invariant violation, similar to bugs where a counter is read but never written, leading to unlimited resource consumption. From a user’s perspective, votes may appear to be accepted without limit, resulting in unexpected allocation results, such as a proposal receiving an implausibly high number of votes or a funding round being awarded to an unintended recipient, contrary to the expectation that each participant’s voting power is capped.
