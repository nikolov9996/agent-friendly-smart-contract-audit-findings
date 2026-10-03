---
id: 25750
severity: "Medium"
---

# Strategy::checkPoolActivity() incorrect check leads to vulnerable price

## Description



## Proof of Concept

The following function is used when cardinality is increased in the pool.

```solidity
    function grow(
        Observation[65535] storage self,
        uint16 current,
        uint16 next
    ) internal returns (uint16) {
        require(current > 0, 'I');
        // no-op if the passed next value isn't greater than the current next value
        if (next <= current) return current;
        // store in each slot to prevent fresh SSTOREs in swaps
        // this data will not be used because the initialized boolean is still false
        for (uint16 i = current; i < next; i++) self[i].blockTimestamp = 1;
        return next;
    }
```

## Recommendation

```solidity
            if (timestamp == 1) {
                revert("timestamp 1");
            }
```
