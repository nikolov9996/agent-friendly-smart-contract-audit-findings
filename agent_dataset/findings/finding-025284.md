---
id: 25284
severity: "Low/Info"
---

# StandardGovernor's implementation of quorum is incompatible with Tally

## Description

The [StandardGovernor](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/StandardGovernor.sol>) contract inherits from IGovernor, which states the following:

```solidity
/// @title Minimal OpenZeppelin-style, Tally-compatible governor. interface IGovernor is IERC6372, IERC712 {
```

But the StandardGovernor contract implements quorum functions in the following way:

```solidity
/// @inheritdoc IGovernor
function quorum() external pure returns (uint256) {
    return 0;
}
/// @inheritdoc IGovernor
function quorum(uint256) external pure returns (uint256) {
    return 0;
}
```

The [documentation](<https://docs.tally.xyz/user-guides/tally-contract-compatibility/openzeppelin-governor#quorum>) from Tally states that it "needs the quorum to calculate if a proposal has passed." Returning quorum as zero, even though that's not the quorum threshold's value, will not only break some compatibility with Tally, but it also might bring about unexpected outputs to other smart contracts within the Ethereum ecosystem expecting the StandardGovernor to follow full Tally compatibility, as stated in IGovernor, thus breaking modularity.

## Proof of Concept

No PoC provided.

## Recommendation

Consider properly implementing the quorum functions. Optionally, be explicit about this lack of compatibility.
