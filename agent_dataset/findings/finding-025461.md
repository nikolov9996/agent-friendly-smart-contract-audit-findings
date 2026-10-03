---
id: 25461
severity: "Low/Info"
---

# Using low level pop is not recommended

## Description

Using assembly blocks in solidity isn't recommended, unless it presents as obvious advantage, usually an optimization, that can't be performed with standard solidity.

[Line 214](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouseBase.sol#L214>) of the ClearingHouseBase contract implements such an assembly block, popping an element from a memory array by overriding its size.

The issue is that this line, not only makes the code harder to read and audit, but also doesn't seem to present any real advantage compared to simply using the pop() function on the array in storage. In regards to gas, this approach actually tends to underperform a much simpler manipulation of the storage array, as proven by the following benchmarks:

```solidity
pragma solidity 0.8.19;
contract test {
    mapping(uint256 trader => mapping(uint256 amm => uint256[] ids))
    internal reduceOnlyOrders;
    constructor() {
        reduceOnlyOrders[0][0].push(8);
        reduceOnlyOrders[0][0].push(9);
    }
    // execution cost if length = 2 and id_deleted = 9: 13715 gas // execution cost if length = 2 and id_deleted = 8: 16629 gas // execution cost if length = 1: 11211 gas
    function test_function() external {
        uint256 id = 8;
        uint256[] memory linkedOrders = reduceOnlyOrders[0][0];
        if (linkedOrders.length == 0) return;
        if (linkedOrders.length == 1) {
            delete reduceOnlyOrders[0][0];

        } else {
            if (linkedOrders[0] == id) { // if id is first linked order,
swap it
linkedOrders[0] = linkedOrders[1];
}
// pop
assembly { mstore(linkedOrders, sub(mload(linkedOrders), 1)) }
reduceOnlyOrders[0][0] = linkedOrders;
}
}
}
contract test_optimized {
    mapping(uint256 trader => mapping(uint256 amm => uint256[] ids))
    internal reduceOnlyOrders;
    constructor() {
        reduceOnlyOrders[0][0].push(8);
        reduceOnlyOrders[0][0].push(9);
    }
    // execution cost if length = 2 and id_deleted = 9: 13198 gas // execution cost if length = 2 and id_deleted = 8: 16784 gas // execution cost if length = 1: 10879 gas
    function test_function() external {
        uint256 id = 8;
        uint256 length = reduceOnlyOrders[0][0].length;
        if (length == 0) return;
        if (length == 1) {
            delete reduceOnlyOrders[0][0];
        } else {
            // note: reduceOnlyOrders has a max length of 2
            if (reduceOnlyOrders[0][0][0] == id) { // if id is first linked
order, swap it
reduceOnlyOrders[0][0][0] = reduceOnlyOrders[0][0][1];
}
reduceOnlyOrders[0][0].pop();
}
}
}
```

Note: adding a comment stating that the array max size is equal to 2 will also make it easier to understand.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
