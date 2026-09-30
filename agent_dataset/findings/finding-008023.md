---
id: 8023
severity: "High"
---

# Incorrect indexing for bid sorting algorithm

## Description

When an Atlas CallConfig specifies exPostBids == true, all solverOps are simulated on-chain to determine their theoretical bid amount. The solverOps are then sorted and executed in order until a solverOp succeeds. The sorting of the bids is facilitated through the following code:  

```solidity
uint256[] memory sortedOps = new uint256[](solverOps.length);
uint256[] memory bidAmounts = new uint256[](solverOps.length);
uint256 j;
uint256 bidPlaceholder;
for (uint256 i; i < solverOps.length; i++) {
    bidPlaceholder = _getBidAmount(dConfig, userOp, solverOps[i], returnData, key);
    if (bidPlaceholder == 0) {
        unchecked {
            ++j;
        }
        continue;
    } else {
        bidAmounts[i] = bidPlaceholder;
        for (uint256 k = i - j + 1; k > 0; k--) {
            if (bidPlaceholder > bidAmounts[sortedOps[k - 1]]) {
                sortedOps[k] = sortedOps[k - 1];
                sortedOps[k - 1] = i;
            } else {
                sortedOps[k] = i;
                break;
            }
        }
    }
}
```

Notice that the inner for loop starts with the index k = i - j + 1. Since it's possible that j always remains at 0 (i.e. if all bid simulations succeed), this index may be out-of-bounds for the sortedOps array, which will cause an unintended revert. This indexing can also potentially leave the zeroth index unset, which can later lead to duplicate attempts of the first solverOp.

Here is a proof of concept to show the issue:  

```solidity
// SPDX-License-Identifier: MIT OR Apache-2.0
pragma solidity 0.8.25;
import "hardhat/console.sol";
contract test {
    constructor() {
        uint ol = 2;
        uint256[] memory _getBidAmount = new uint256[](ol);
        _getBidAmount[0] = 6; // works if one of these values is 0
        _getBidAmount[1] = 6;
        uint256[] memory sortedOps = new uint256[](ol);
        uint256[] memory bidAmounts = new uint256[](ol);
        uint256 j;
        uint256 bidPlaceholder;
        for (uint256 i; i < ol; i++) {
            bidPlaceholder = _getBidAmount[i];
            if (bidPlaceholder == 0) {
                unchecked { ++j;}
                continue;
            } else {
                bidAmounts[i] = bidPlaceholder;
                for (uint256 k = i - j + 1; k > 0; k--) {
                    if (bidPlaceholder > bidAmounts[sortedOps[k - 1]]) {
                        sortedOps[k] = sortedOps[k - 1];
                        sortedOps[k - 1] = i;
                    } else {
                        sortedOps[k] = i;
                        break;
                    }
                }
            }
        }
        uint total = ol - j;
        console.log("total",total);
        for (uint256 i; i < total; i++) {
            console.log(i,sortedOps[i],bidAmounts[sortedOps[i]]);
        }
    }
}
```

## Proof of Concept

no poc

## Recommendation

Rework the indexing of this sorting algorithm. The following code snippet is one possible implementation of the inner for loop:

```solidity
// `k` starts at the left-most unfilled location
uint256 k = i - j;
while (k > 0 && bidPlaceholder > bidAmounts[sortedOps[k - 1]]) {
    sortedOps[k] = sortedOps[k - 1];
    k--;
}
sortedOps[k] = i;
```

Alternatively, consider reworking a larger part of this code to make the on-chain sorting easier to understand.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one indexing error in the on‑chain sorting routine that orders solver operations by their simulated bid amount when exPostBids is enabled. The algorithm builds two parallel arrays, one for the indices of the operations (sortedOps) and one for the corresponding bid amounts (bidAmounts). A counter j tracks how many operations have a zero bid and are skipped. For each operation the inner loop starts with k = i - j + 1 and writes to sortedOps[k] and sortedOps[k-1]. If no operation is skipped (j stays zero) the expression i - j + 1 evaluates to i + 1, which for the first iteration (i = 0) yields k = 1. Because sortedOps was allocated with length equal to the number of operations, the highest valid index is length‑1. When i equals the last index, k becomes length, which is out of bounds and triggers a revert. In addition, the algorithm may never write to index 0, leaving it unset and causing the first operation to be considered twice later in the execution phase. The root cause is the incorrect calculation of the insertion point in the insertion‑sort style loop, mixing the number of skipped entries with the current loop index. An attacker or a benign user can trigger the bug simply by submitting a batch of operations where all simulated bids are non‑zero. The contract will attempt to sort the bids, hit the out‑of‑bounds write, and revert the whole transaction. From the user’s perspective the transaction fails with no explicit error message; the expected outcome – a successful solver operation selected by the highest bid – never occurs, and the user may see that no funds are transferred or that the operation appears to have been ignored. The protocol’s auction mechanism therefore loses its ability to choose the most profitable solver, potentially leaving the system idle or forcing a fallback path that may be less efficient or more expensive. The issue was discovered during a manual security review of the Fastlane contract suite, where the auditor noticed that the inner loop uses i‑j+1 as the starting index and reasoned that when j is zero the index can exceed the array bounds. A proof‑of‑concept contract reproduces the revert by initializing two non‑zero bids and executing the same sorting logic. Because the failure occurs only when all bids are non‑zero, it can be hard to notice in routine testing that includes zero‑bid cases. The revert does not emit a custom error, so developers may misinterpret the failure as a generic out‑of‑gas or network issue. Moreover, the subtle duplication of the first operation can lead to inconsistent execution ordering that is not obvious from logs. The correct fix is to compute the insertion point without the extra “+1” and to shift existing entries only while the target position is greater than zero and the new bid is larger than the previous entry. A safe implementation uses a while loop that starts at k = i - j and moves elements one position to the right until the proper place is found, then writes the current index at k. Re‑architecting the sorting routine to use a standard insertion sort or a library function would also eliminate the off‑by‑one error and make the code easier to audit.
