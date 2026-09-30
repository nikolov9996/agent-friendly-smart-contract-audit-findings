---
id: 21623
severity: "High"
---

# `GlobalConfiguration::removeCollateralFromLiquidationPriority` corrupts the collateral priority order resulting in incorrect order of collateral liquidation

## Description

`GlobalConfiguration` [uses](https://github.com/zaros-labs/zaros-core-audit/blob/de09d030c780942b70f1bebcb2d245214144acd2/src/perpetuals/leaves/GlobalConfiguration.sol#L46) OpenZeppelin's `EnumerableSet` to store the collateral liquidation priority order:
```solidity
/// @param collateralLiquidationPriority The set of collateral types in order of liquidation priority
struct Data {
    /* snip....*/
    EnumerableSet.AddressSet collateralLiquidationPriority;
}
```
But OpenZeppelin's `EnumerableSet` explicitly provides [no guarantees](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L16) that the order of elements is [preserved](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L131-L141) and its `remove` function uses the [swap-and-pop](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L89-L91) method for performance reasons which *guarantees* that order will be corrupted when collateral is removed.
When one collateral is removed from the set, the collateral priority order will become corrupted. This will result in the incorrect collateral being prioritized for liquidation and other functions within the protocol.

## Proof of Concept

Check out this stand-alone Foundry PoC:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import { EnumerableSet } from "openzeppelin-contracts/utils/structs/EnumerableSet.sol";

import "forge-std/Test.sol";

// run from base project directory with:
// forge test --match-contract SetTest
contract SetTest is Test {
    using EnumerableSet for EnumerableSet.AddressSet;

    EnumerableSet.AddressSet collateralLiquidationPriority;

    function test_collateralLiquidationPriorityReorders() external {
        // create original order of collateral liquidation priority
        address collateralType1 = address(1);
        address collateralType2 = address(2);
        address collateralType3 = address(3);
        address collateralType4 = address(4);
        address collateralType5 = address(5);

        // add them to the set
        collateralLiquidationPriority.add(collateralType1);
        collateralLiquidationPriority.add(collateralType2);
        collateralLiquidationPriority.add(collateralType3);
        collateralLiquidationPriority.add(collateralType4);
        collateralLiquidationPriority.add(collateralType5);

        // affirm length and correct order
        assertEq(5, collateralLiquidationPriority.length());
        assertEq(collateralType1, collateralLiquidationPriority.at(0));
        assertEq(collateralType2, collateralLiquidationPriority.at(1));
        assertEq(collateralType3, collateralLiquidationPriority.at(2));
        assertEq(collateralType4, collateralLiquidationPriority.at(3));
        assertEq(collateralType5, collateralLiquidationPriority.at(4));

        // everything looks good, the collateral priority is 1->2->3->4->5

        // now remove the first element as we don't want it to be a valid
        // collateral anymore
        collateralLiquidationPriority.remove(collateralType1);

        // length is OK
        assertEq(4, collateralLiquidationPriority.length());

        // we now expect the order to be 2->3->4->5
        // but EnumerableSet explicitly provides no guarantees on ordering
        // and for removing elements uses the `swap-and-pop` technique
        // for performance reasons. Hence the 1st priority collateral will
        // now be the last one!
        assertEq(collateralType5, collateralLiquidationPriority.at(0));

        // the collateral priority order is now 5->2->3->4 which is wrong!
        assertEq(collateralType2, collateralLiquidationPriority.at(1));
        assertEq(collateralType3, collateralLiquidationPriority.at(2));
        assertEq(collateralType4, collateralLiquidationPriority.at(3));
    }
}
```

## Recommendation

Use a data structure that preserves order to store the collateral liquidation priority.
Alternatively OpenZeppelin's `EnumerableSet` can be used but its `remove` function should never be called - when removing collateral the entire set must be emptied and a new set configured with the previous ordering minus the removed element.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An issue exists in the protocol's global configuration component where the list that determines the order in which different collateral types are liquidated is stored in an OpenZeppelin EnumerableSet. EnumerableSet is designed for constant‑time add, remove and existence checks, but it explicitly does not preserve the insertion order of elements. Its remove operation implements a swap‑and‑pop technique: the element to be deleted is replaced by the last element in the internal array and the array length is reduced. Consequently, when a collateral type is removed from the priority set, the relative ordering of the remaining collaterals is shuffled. The contract assumes that the set maintains a stable ranking (for example, collateral A is always liquidated before collateral B), and many downstream functions read the element at index 0 as the highest‑priority collateral. After a removal, the contract may mistakenly select a lower‑priority or even an unintended collateral as the first to be liquidated. This can cause the protocol to liquidate assets that are less valuable or that the user did not intend to be used, potentially leading to higher slippage, loss of capital, or failure to meet liquidation requirements. The bug manifests only when a collateral type is deregistered or disabled; if the set is never modified, the ordering appears correct, making the problem easy to miss during casual testing. It was discovered during a formal audit when the auditors wrote a small Foundry test that added several addresses to the set, removed the first one, and observed that the element at index 0 changed to the last address, confirming the swap‑and‑pop behavior. Because the contract does not emit an explicit warning and the UI typically shows only the list of active collaterals, users may see a collateral disappear from the configuration page while the liquidation engine suddenly starts using a different asset, leading to unexpected funds disappear or wrong asset liquidated symptoms. The vulnerability belongs to the class of ordering‑assumption bugs where a data structure that does not guarantee order is used to enforce business logic that relies on a stable sequence. To remediate, the protocol should replace the EnumerableSet with a structure that preserves insertion order, such as an array with explicit index management or a linked list, or redesign the removal process to rebuild the set without invoking the swap‑and‑pop operation. Ensuring that the priority list remains consistent after any modification will align the contract’s behavior with the expected liquidation policy and prevent accidental liquidation of unintended collateral.
