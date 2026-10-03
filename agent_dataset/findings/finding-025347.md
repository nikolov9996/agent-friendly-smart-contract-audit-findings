---
id: 25347
severity: "Low/Info"
---

# Throughout code-base: missing address checks.

## Description

Whenever addresses change in the code, it's important to be careful about the possibility of setting the wrong address. The following occurrences could be dangerous in this regard

```solidity
- MapleProxyFactory, setGlobals(...)
- MapleGlobals, setMapleTreasury(...)
```

- Fixed-term-loan-private, the [constructor of](<https://github.com/maple-labs/fixed-term-loan-private/blob/670e9fe6dea857c8a0b203893fb32b66018f87d8/contracts/MapleLoanFeeManager.sol#L46>) MapleLoanFeeManager

## Proof of Concept

No PoC provided.

## Recommendation

Two options were suggested:

- use the setPending-accept pattern
- don't change addresses, given that the contracts are upgradeable
