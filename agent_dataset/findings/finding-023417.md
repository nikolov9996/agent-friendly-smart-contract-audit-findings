---
id: 23417
severity: "High"
---

# swap-and-pop without index fix-up corrupts position’s fungible array

## Description

Position tracks fungible collateral in two places that must stay in sync:

```solidity
struct Position {
    address owner;
    uint256 debtShare;
    Fungible[] fungibles; // compact list of held assets
    NonFungible[] nonFungibles;
    mapping(Fungible => FungibleState) fungibleStates; // per-asset {index,balance}
}
```

Invariant: for every asset a in fungibles[k], we must have fungibleStates[a].index == k+1 (the library uses 1‑based indexes; index == 0 means “not present”).

When an asset’s balance goes to zero, `Position::removeFungible` tries to “swap-and-pop”: move the last array element into the removed slot and shrink the array. The code does the array move, but forgets to update the moved element’s cached index in `fungibleStates`:

```solidity
// remove a fungible from the fungibles array
assembly ("memory-safe") {
    let slot := add(self.slot, FUNGIBLES_OFFSET)
    let len := sload(slot)
    mstore(0x00, slot)
    let dataSlot := keccak256(0x00, 0x20)
    if iszero(eq(index, len)) {
        // overwrite removed slot with the last element (swap)
        sstore(add(dataSlot, sub(index, 1)), sload(add(dataSlot, sub(len, 1))))
    }
    // pop
    sstore(add(dataSlot, sub(len, 1)), 0)
    sstore(slot, sub(len, 1))
}
```

What’s missing is the index fix‑up for the element that got moved down from the tail. Without it, `fungibleStates[moved].index` still points to the old tail index.

Why this corrupts state:
1. Start with `fungibles = [A, B, C]` and `index(A)=1, index(B)=2, index(C)=3`
2. Remove A (index=1). Code copies last element C into slot 0 and pops the array: `fungibles = [C, B]`, length = 2. But `index(C)` is still 3 (stale).
3. Later, remove C. The function trusts the stale `index(C)=3`:
   • It tries to “swap-and-pop” using index = 3 and len = 2, which makes it copy B into slot index‑1 = 2 (past the new end), then pops slot 1.
   • Net effect: B silently vanishes from the active array (length becomes 1 and `fungibles[0]` may still be C), while `fungibleStates[B]` still shows a positive balance.

This desynchronizes the array and mapping, leading to:
- “Remove X, but actually lose Y” behavior (wrong element disappears).
- “Ghost” balances left in the mapping not represented in the array (appraisal that iterates `fungibles` under‑counts value).
- Future removals/operations using stale indexes read/write the wrong slots.

Impact
- Inconsistent state between `fungibles[]` and `fungibleStates` (stale or duplicate indexes).
- Removing token X can unexpectedly remove token Y from the array.
- Enumeration‑based logic (e.g., valuation/appraisal that iterates `fungibles[]`) may under‑ or over‑count positions, leading to incorrect health/accounting decisions.

## Proof of Concept

```solidity
function test_removeFungible_missingIndexFixup() public {
    BaseERC20Mock token = _newAsset(18);
    Fungible fungible = Fungible.wrap(address(token));
    // --- arrange: two fungibles in the same position ---
    token.mint(address(this), 1 ether);
    token.approve(address(licredityRouter), 1 ether);
    uint256 positionId = licredityRouter.open();
    // deposit native (will be fungibles[0])
    licredityRouter.depositFungible{value: 0.5 ether}(positionId, Fungible.wrap(ChainInfo.NATIVE), 0.5 ether);
    // deposit ERC20 (will be fungibles[1])
    licredityRouter.depositFungible(positionId, fungible, 1 ether);
    // --- discover storage slots we need (once per test is fine) ---
    // We'll find:
    // - the base slot of positions[positionId] (self.slot)
    // - the fungibleStates mapping base slot: self.slot + FUNGIBLE_STATES_OFFSET
    // - the fungibles array slot: self.slot + FUNGIBLES_OFFSET
    (
        ,
        uint256 fungibleStatesBase,
        uint256 fungiblesArraySlot
    ) = _locatePositionFungibleStateAndArraySlots(positionId, address(licredity), address(token));
    // Sanity: array length is 2
    uint256 lenBefore = uint256(vm.load(address(licredity), bytes32(fungiblesArraySlot)));
    assertEq(lenBefore, 2, "pre: fungibles length should be 2");
    // Pre-read the packed FungibleState word for the ERC20 (this includes index + balance)
    bytes32 stateBefore = _loadFungibleState(
        address(licredity),
        fungibleStatesBase,
        address(token)
    );
    // Also read the array’s first element (should be native) and second (should be ERC20)
    bytes32 dataSlot = keccak256(abi.encodePacked(bytes32(fungiblesArraySlot)));
    bytes32 arr0Before = vm.load(address(licredity), dataSlot); // [0]
    bytes32 arr1Before = vm.load(address(licredity), bytes32(uint256(dataSlot) + 1)); // [1]
    assertEq(address(uint160(uint256(arr0Before))), address(0), "pre: [0] must be native");
    assertEq(address(uint160(uint256(arr1Before))), address(token), "pre: [1] must be ERC20");
    // --- act: remove the non-last fungible (native) fully -> triggers swap-and-pop ---
    licredityRouterHelper.withdrawFungible(positionId, address(this), ChainInfo.NATIVE, 0.5 ether);
    // --- assert: array element moved down, BUT ERC20's state word did not change (index not fixed up)
    // array length dropped to 1
    uint256 lenAfter = uint256(vm.load(address(licredity), bytes32(fungiblesArraySlot)));
    assertEq(lenAfter, 1, "post: fungibles length should be 1");
    // array[0] should now hold the ERC20 address (moved from index 1 -> 0)
    bytes32 arr0After = vm.load(address(licredity), dataSlot);
    assertEq(address(uint160(uint256(arr0After))), address(token), "post: [0] must be ERC20");
    // read ERC20's packed state again
    bytes32 stateAfter = _loadFungibleState(
        address(licredity),
        fungibleStatesBase,
        address(token)
    );
    // Because we removed NATIVE entirely and did not touch ERC20 balance,
    // a correct implementation would ONLY change the ERC20's *index* inside the word.
    // Since the code does not fix up the index, the word stays identical.
    assertEq(stateAfter, stateBefore, "post: ERC20 FungibleState word unchanged (index not fixed up)");
}

// Probe storage to find (self.slot, self.slot + FUNGIBLE_STATES_OFFSET, self.slot + FUNGIBLES_OFFSET).
// Heuristic: after two deposits, the fungibles array length is 2 and
// the fungibleStates mapping for both keys (native, token) are non-zero.
function _locatePositionFungibleStateAndArraySlots(
    uint256 positionId,
    address target,
    address erc20
)
    internal
    view
    returns (uint256 selfSlot, uint256 fungibleStatesBase, uint256 fungiblesArraySlot)
{
    // positions is a mapping at some slot S. The Position struct lives at keccak256(positionId, S).
    // We search S[0..160], and offsets off[0..24] for the two sub-structures.
    for (uint256 S = 0; S <= 160; S++) {
        bytes32 self = keccak256(abi.encode(positionId, S));
        // try to locate the mapping base (self + offMap) by checking both keys are non-zero
        for (uint256 offMap = 0; offMap <= 24; offMap++) {
            uint256 candMapBase = uint256(self) + offMap;
            bytes32 nativeState = _loadFungibleState(target, candMapBase, address(0));
            bytes32 erc20State = _loadFungibleState(target, candMapBase, erc20);
            if (nativeState != bytes32(0) && erc20State != bytes32(0)) {
                // now also find the array slot (self + offArr) where length == 2
                for (uint256 offArr = 0; offArr <= 24; offArr++) {
                    uint256 candArrSlot = uint256(self) + offArr;
                    uint256 len = uint256(vm.load(target, bytes32(candArrSlot)));
                    if (len == 2) {
                        // double-check array contents look like [native, erc20]
                        bytes32 dataSlot = keccak256(abi.encodePacked(bytes32(candArrSlot)));
                        address a0 = address(uint160(uint256(vm.load(target, dataSlot))));
                        address a1 = address(
                            uint160(uint256(vm.load(target, bytes32(uint256(dataSlot) + 1))))
                        );
                        if (a0 == address(0) && a1 == erc20) {
                            return (uint256(self), candMapBase, candArrSlot);
                        }
                    }
                }
            }
        }
    }
    revert("could not locate position/fungible storage layout");
}

function _loadFungibleState(address target, uint256 mapBaseSlot, address asset)
    internal
    view
    returns (bytes32)
{
    // storage key for mapping: keccak256(abi.encode(key, slot))
    bytes32 key = keccak256(
        abi.encodePacked(bytes32(uint256(uint160(asset))), bytes32(mapBaseSlot))
    );
    return vm.load(target, key);
}

receive() external payable {}
```

## Recommendation

Recommended Mitigation: Update index to point at the moved entry:

```solidity
// (conceptually)
Fungible moved = fungibles[len-1];
fungibles[index-1] = moved;
fungibles.pop();
// fix cached index for the moved element
fungibleStates[moved].index = index; // 1-based
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an array‑mapping desynchronization caused by a swap‑and‑pop removal routine that fails to update the cached index of the element moved from the tail of the fungibles array. In the Position struct, each fungible asset is stored both in a compact array (fungibles) and in a mapping (fungibleStates) that holds the asset’s index (1‑based) and balance. The invariant requires that for every asset a at position k in the array, fungibleStates[a].index equals k+1. When an asset’s balance drops to zero, the removeFungible function executes an assembly block that swaps the last array element into the slot of the removed asset and then pops the array. The code correctly overwrites the storage slot and reduces the length, but it never writes the new index back into fungibleStates for the element that was moved. As a result, the moved element retains a stale index that points to its former tail position. This stale index is later used by subsequent removals, causing the routine to calculate an out‑of‑bounds source slot or to overwrite the wrong entry. Consequently, an asset that should remain in the position can be silently removed from the array while its balance stays in the mapping, producing “ghost” balances that are invisible to enumeration‑based logic such as collateral valuation or health‑factor calculation. The bug manifests only when a fungible is removed while its balance is zero, i.e., when swap‑and‑pop is triggered. Users see symptoms like missing assets in UI listings, unexpected drops in reported collateral value, or transaction reverts due to invalid storage accesses. The protocol’s accounting becomes unreliable, potentially leading to incorrect liquidation decisions. The issue was discovered during a security audit that inspected storage layout and observed that after removing a non‑last fungible, the array length decreased but the index stored for the remaining asset did not change. The problem is hard to notice because the array length appears correct and no direct revert occurs; only higher‑level logic that relies on the invariant fails. The proper fix is to update fungibleStates[moved].index to the new 1‑based position after the swap, or to replace the low‑level assembly with a safer Solidity implementation that maintains the invariant. Restoring the invariant eliminates the desynchronization, ensures accurate enumeration, and prevents accidental loss of asset visibility.
