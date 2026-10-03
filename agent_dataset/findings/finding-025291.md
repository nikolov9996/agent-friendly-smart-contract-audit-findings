---
id: 25291
severity: "Low/Info"
---

# Proposals in the same voting period can have different ids but do the same

## Description

In the [BatchGovernor](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/BatchGovernor.sol>) contract, a new proposal will generate a proposal id by using the

```solidity
calldata and the vote start. The _revertIfInvalidCalldata function makes sure the
function selector is allowed (implemented in StandardGovernor, EmergencyGovernor and
```

ZeroGovernor). The issue is that the proposal calldata can have appended "dust" bytes in the end and it will still be considered valid. Anyone can create a proposal generating a different id but doing functionally the same thing as another existing proposal, because the "dust" bytes will be ignored on the execution moment but not on the id generation.

For example, to propose the call EmergencyGovernor.setStandardProposalFee(10), the 2 following calldata values will generate 2 different proposal ids accomplishing the same thing:

- 0xb5775125000000000000000000000000000000000000000000000000000000000000000a
- 0xb5775125000000000000000000000000000000000000000000000000000000000000000aff ffff Allowing different proposal ids to accomplish the same thing in the same voting period can potentially force the voters to randomly decide between the 2 valid proposals, which might break the voting quorum. Because the EmergencyGovernor doesn't have a proposal fee (StandardGovernor has one), it is easier to spam with a number of different proposals doing the same thing as a legitimate one, which can cause confusion among voters and split the quorum.

## Proof of Concept

No PoC provided.

## Recommendation

Consider checking the calldata size in the function _revertIfInvalidCalldata. For example, the implementation in the StandardGovernor would be the following:

```solidity
function _revertIfInvalidCalldata(bytes memory callData_) internal pure
override {
    bytes4 func_ = bytes4(callData_);
    uint256 length = callData_.length;
    if ( !(func_ == this.addToList.selector && length == 68) && !(func_ == this.removeFromList.selector && length == 68) && !(func_ == this.removeFromAndAddToList.selector && length == 100) && !(func_ == this.setKey.selector && length == 68) && !(func_ == this.setProposalFee.selector && length == 36) ) revert InvalidCallData();
}
```
