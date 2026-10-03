---
id: 25072
severity: "Crit/High"
---

# DoSed Voter::finalize() due to unbounded pending removals lacking a batch argument variable

## Description



## Proof of Concept

Note `Voter.sol::_processPendingRemovals()`:

```solidity
function _processPendingRemovals(uint256 ep) internal {
    address[] memory toRemove = pendingRemovals[ep];
    for (uint256 i = 0; i < toRemove.length; i++) {
        address addr = toRemove[i];
        uint256 idx = autoIndex[addr];
        if (idx > 0) {
            _removeAutoVoter(addr, idx - 1);
        }
    }
    delete pendingRemovals[ep];
}
```

## Recommendation

Send a batch argument, to avoid OOG revert.
