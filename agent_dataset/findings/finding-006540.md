---
id: 6540
severity: "Critical"
---

# Overflow in SegmentedSegmentTree464

## Description

SegmentedSegmentTree464.update needs to perform an overflow check in case the new value is greater than the old value. This overflow check is done when adding the new difference to each node in each layer (using addClean). Furthermore, there's a final overflow check by adding up all nodes in the first layer in total(core).
However, in total, the nodes in individual groups are added using DirtyUint64.sumPackedUnsafe:
```solidity
function total(Core storage core) internal view returns (uint64) {
    return DirtyUint64.sumPackedUnsafe(core.layers[0][0], 0, _C)
        + DirtyUint64.sumPackedUnsafe(core.layers[0][1], 0, _C);
}
```
The nodes in a group can overflow without triggering an overflow & revert. The impact is that the order book depth and claim functionalities break for all users.
```solidity
// SPDX-License-Identifier: BUSL-1.1
pragma solidity ^0.8.0;
import "forge-std/Test.sol";
import "forge-std/StdJson.sol";
import "../../contracts/mocks/SegmentedSegmentTree464Wrapper.sol";
contract SegmentedSegmentTree464Test is Test {
    using stdJson for string;
    uint32 private constant _MAX_ORDER = 2**15;
    SegmentedSegmentTree464Wrapper testWrapper;
    function setUp() public {
        testWrapper = new SegmentedSegmentTree464Wrapper();
    }
    function testTotalOverflow() public {
        uint64 half64 = type(uint64).max / 2 + 1;
        testWrapper.update(0, half64);
        // map to the right node of layer 0, group 0
        testWrapper.update(_MAX_ORDER / 2 - 1, half64);
        assertEq(testWrapper.total(), 0);
    }
}
```

## Proof of Concept

no poc

## Recommendation

Perform a safe addition for the first layer and rewrite the overflow check.
```solidity
// DirtyUint64.sumPackedSafe still needs to be implemented and should do checked addition
require(
    uint256(DirtyUint64.sumPackedSafe(core.layers[0][0], 0, _C))
        + uint256(DirtyUint64.sumPackedSafe(core.layers[0][1], 0, _C)) <= type(uint64).max,
    "TREE_MAX"
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unsigned‑integer overflow in the first layer of a segmented segment tree that stores order‑book depth values as packed uint64 entries. The tree’s total() function aggregates the two groups of nodes by calling DirtyUint64.sumPackedUnsafe, which adds the packed values without performing any overflow check. When an update writes a value larger than half of the uint64 maximum into two distinct nodes of the same group, the sum of those packed values exceeds type(uint64).max and silently wraps around to zero because the addition is unchecked. This overflow is not caught by the existing overflow guard that only validates the difference added to each node during an update, nor by the final check that adds the two group totals, because both totals have already wrapped. The bug can be exploited by an attacker (or even an honest user) who submits large order amounts that trigger the overflow, causing the contract’s view of total depth to become incorrect – often zero – while the underlying node values remain high. As a result, the order‑book depth reporting, price‑impact calculations, and claim functions that rely on the total depth break for all participants; users may see no available liquidity, receive zero refunds, or be unable to settle positions. The condition occurs whenever the contract processes updates that push any group’s packed sum beyond the 64‑bit limit, which is feasible because the contract does not enforce a per‑group cap. The issue was discovered during a formal audit when a test case updated two nodes with a value just above type(uint64).max/2, causing total() to return zero despite non‑zero inputs. The overflow is hard to notice because individual node values appear correct and no revert is emitted; only the aggregated total is wrong, leading to subtle accounting mismatches. To remediate, the implementation should replace sumPackedUnsafe with a checked addition routine (e.g., sumPackedSafe) and enforce that the combined sum of both groups never exceeds type(uint64).max, causing the transaction to revert if the limit would be breached. This change restores the invariant that the order‑book depth cannot overflow, preserving correct accounting and preventing users from experiencing missing depth or failed claims.
