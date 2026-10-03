---
id: 25443
severity: "Low/Info"
---

# Midnight constructor can use msg.sender instead of reading roleSetter from storage

## Description



## Proof of Concept

## Vulnerability Detail

In the [constructor](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/Midnight.sol#L135>):

```solidity
constructor() {
    roleSetter = msg.sender;
    emit EventsLib.Constructor(roleSetter);
}
```

`roleSetter` was just assigned `msg.sender`, so the emit reads back from storage instead of using the already-available `msg.sender` from the calldata.

## Impact

Wastes gas on an unnecessary SLOAD in the constructor.

## Code Snippet

[https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/Midnight.sol#L133-L136](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/src/Midnight.sol#L133-L136>)

## Recommendation

```solidity
constructor() {
    roleSetter = msg.sender;
    emit EventsLib.Constructor(msg.sender);
}
```
