---
id: 25200
severity: "Low/Info"
---

# Mismatching calldata in _crossTransferWithCalldata(...) and xReceive(...) in ConnextRouter

## Description

Users can bridge assets by inserting an Action.XTransferWithCall action, with calldata specified in the args field. The calldata in _crossTransferWithCalldata(...) and _getBeneficiaryFromCalldata(...) is decoded as :

```solidity
(Action[] memory actions, bytes[] memory args,) = abi.decode(callData, (Action[], bytes[], uint256));
```

Whereas in xReceive(...), it lacks the last uint256:

```solidity
(Action[] memory actions, bytes[] memory args) = abi.decode(callData, (Action[], bytes[]));
```

## Proof of Concept

[https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/EncodingCalldata.t.sol#L12](<https://github.com/threesigmaxyz/fuji-issues-external/blob/master/test/POC/EncodingCalldata.t.sol#L12>)

## Recommendation

Remove the last uint256 parameter from being decoded, as it is not being used.
