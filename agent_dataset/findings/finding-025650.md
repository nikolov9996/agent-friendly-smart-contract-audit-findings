---
id: 25650
severity: "Medium"
---

# An attacker may DoS user Fluid balance increases by frontrunning FluidLocker::claim() calls and calling EP_PROGRAM_MANAGER::batchUpdateUserUnits() directly

## Description



## Proof of Concept

The only way to collect the Locker to the program pool is by calling `FluidLocker::claim()` which may be DoSed by calling EP_PROGRAM_MANAGER.updateUserUnits()` directly using the same signature.

```solidity
function claim(uint256 programId, uint256 totalProgramUnits, uint256 nonce, bytes memory stackSignature)
    external
    nonReentrant
{
    // Get the corresponding program pool
    ISuperfluidPool programPool = EP_PROGRAM_MANAGER.getProgramPool(programId);

    if (!FLUID.isMemberConnected(address(programPool), address(this))) {
        // Connect this locker to the Program Pool
        FLUID.connectPool(programPool);
    }

    // Request program manager to update this locker's units
    EP_PROGRAM_MANAGER.updateUserUnits(lockerOwner, programId, totalProgramUnits, nonce, stackSignature);

    emit IFluidLocker.FluidStreamClaimed(programId, totalProgramUnits);
}
```

## Recommendation

The locker should have a separate method to connect to the pool.
