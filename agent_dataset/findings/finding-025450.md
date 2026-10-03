---
id: 25450
severity: "Low/Info"
---

# submit() could be more verbose when a selector has been abdicated

## Description



## Proof of Concept

## Vulnerability Detail

`VaultV2::abdicateSubmit()` sets the timelock to the maximum, making the `submit()` function overflow to disable function calls with this selector.

```solidity
    function abdicateSubmit(bytes4 selector) external {
        timelocked();
        timelock[selector] = type(uint256).max;
        emit EventsLib.AbdicateSubmit(selector);
    }
```

## Impact

Error handling is not very verbose

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R384](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R384>)

## Recommendation

Add an error message.
