---
id: 25633
severity: "Low/Info"
---

# nativeFeeProvided < totalNativeRequired check in BridgeDeBridge::bridgeDeBridgeWithFee is incorrect

## Description



## Proof of Concept

## Vulnerability Detail

The source bridge enforces that the native fee provided is exactly the amount + fee, [link](<https://github.com/debridge-finance/dln-contracts/blob/main/contracts/DLN/DlnSource.sol#L585-L587>). Hence, this check is not accurate.

```solidity
if (_orderCreation.giveTokenAddress == address(0)) {
    if (msg.value != _order.giveAmount + globalFixedNativeFee) revert MismatchNativeGiveAmount();
}
```

## Impact

There is no impact other than some extra gas cost and readability, since the call will revert later.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/5/files#diff-eba31f672a0e150d33e98354d7cada4c4eb270fda831d5b53382b7eaae395260R166](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/5/files#diff-eba31f672a0e150d33e98354d7cada4c4eb270fda831d5b53382b7eaae395260R166>)

## Recommendation

Change the check to be `!=`.
