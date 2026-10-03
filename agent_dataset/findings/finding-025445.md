---
id: 25445
severity: "Low/Info"
---

# testReturnJumps asserts the wrong ratio direction

## Description



## Proof of Concept

## Vulnerability Detail

In [`TickLibTest.sol#L33`](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/test/TickLibTest.sol#L33>):

```solidity
function testReturnJumps() public pure {
    for (uint256 i = 220; i <= 770; i++) {
        uint256 previousReturn = _return(TickLib.tickToPrice(i - 1));
        uint256 currentReturn = _return(TickLib.tickToPrice(i));
        assertApproxEqRel(
            currentReturn.mulDivDown(1e18, previousReturn), 1.025e18, 0.1e18, ...
        );
    }
}
```

`_return(price) = 1e18 / price - 1`, which is `1/price - 1`. Since `tickToPrice` is monotonically increasing, a higher tick gives a higher price and a lower return. Therefore `currentReturn / previousReturn = 1/1.025 ~= 0.9756`, not `1.025`.

The assertion passes because `|0.9756 - 1.025| / 1.025 ~= 4.8%`, which is within the 10% relative tolerance.

## Impact

The test does not verify what it intends to. The expected value should be `~0.9756e18` (i.e. `1/1.025`), or the ratio should be flipped to `previousReturn / currentReturn`.

## Code Snippet

[https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/test/TickLibTest.sol#L28-L36](<https://github.com/sherlock-audit/2026-04-morpho-midnight-apr-6th-2026/blob/main/morpho-org__midnight/test/TickLibTest.sol#L28-L36>)

## Recommendation

Fix the assertion to check the correct ratio:

```solidity
assertApproxEqRel(
    previousReturn.mulDivDown(1e18, currentReturn), 1.025e18, 0.01e18, ...
);
```
