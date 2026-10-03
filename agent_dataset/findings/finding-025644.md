---
id: 25644
severity: "Crit/High"
---

# Fontaine never stops the flows to the tax and recipient, so the buffer component of the flows will be lost

## Description



## Proof of Concept

Add the following logs to `Fontaine.sol` and run `forge test --mt testVestUnlock -vvvv`. `Alice` sends `10_000e18` to the fontaine, but only `9996.8e18` are left in the fontaine as a part of them are reserved for the buffer which will never be collected back.

```solidity
function initialize(address unlockRecipient, int96 unlockFlowRate, int96 taxFlowRate) external initializer {
    // Ensure recipient is not a SuperApp
    if (ISuperfluid(FLUID.getHost()).isApp(ISuperApp(unlockRecipient))) revert CANNOT_UNLOCK_TO_SUPERAPP();

    console2.log("fontaine balance pre distributeFlow", FLUID.balanceOf(address(this)));

    // Distribute Tax flow to Staker GDA Pool
    FLUID.distributeFlow(address(this), TAX_DISTRIBUTION_POOL, taxFlowRate);

    console2.log("fontaine balance pre createFlow", FLUID.balanceOf(address(this)));

    // Create the unlocking flow from the Fontaine to the locker owner
    FLUID.createFlow(unlockRecipient, unlockFlowRate);

    console2.log("fontaine balance after createFlow", FLUID.balanceOf(address(this)));
}
```

## Impact

The recipient and the tax distribution pool take the loss as they do not receive all their funds (the deposit buffer is never sent to them).

## Recommendation

Add a way to stop the flow and receive the deposit back.
