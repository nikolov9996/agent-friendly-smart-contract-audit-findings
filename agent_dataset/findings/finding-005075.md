---
id: 5075
severity: "High"
---

# Liquidated person's debts are not reduced in liquidation

## Description

After liquidation, the liquidator's TCAPV2 is burned to repay the liquidated person's debts. However, during liquidation, the modifyPosition() function is not called to update the position of the liquidated person to reduce the debt, which would result in the liquidated person being able to be liquidated repeatedly until the collateral goes to 0:
```solidity
pocket.withdraw(user, liquidationReward, msg.sender);
TCAPV2.burn(msg.sender, burnAmount);
emit Liquidated(msg.sender, user, pocketId, liquidationReward, burnAmount);
```

## Proof of Concept

The proof of concept shows that after liquidation, the collateral is 0 and the debt remains unchanged:
```solidity
function test_POC() public {
    address user = address(0xb0b);
    uint amount = 1e18;
    vm.assume(user != address(0) && user != address(vaultProxyAdmin));
    uint256 depositAmount = deposit(user, amount);
    vm.assume(depositAmount > 0);
    vm.prank(user);
    uint256 mintAmount = bound(amount, 1, depositAmount);
    vault.mint(pocketId, mintAmount);
    uint256 collateralValue = vault.collateralValueOfUser(user, pocketId);
    console.logUint(collateralValue); // 1000e18
    uint256 mintValue = vault.mintedValueOf(mintAmount);
    console.logUint(mintValue); // 1000e18
    uint256 multiplier = mintValue * 10_000 / (collateralValue);
    vm.assume(multiplier > 1);
    feed.setMultiplier(multiplier - 1);
    tCAPV2.mint(address(this), mintAmount);
    vm.expectEmit(true, true, true, true);
    emit IVault.Liquidated(address(this), user, pocketId, depositAmount, mintAmount);
    console.logUint(vault.mintedValueOfUser(user,pocketId)); // 1000e18
    collateralValue = vault.collateralValueOfUser(user, pocketId);
    console.logUint(collateralValue); // 99.9e18
    vault.liquidate(user, pocketId, mintAmount);
    collateralValue = vault.collateralValueOfUser(user, pocketId);
    console.logUint(collateralValue); // 0
    console.logUint(vault.mintedValueOfUser(user,pocketId)); // 1000e18
}
```

## Recommendation

Change to
```solidity
$.modifyPosition(_toMintId(user, pocketId), -burnAmount.toInt256());
pocket.withdraw(user, liquidationReward, msg.sender);
TCAPV2.burn(msg.sender, burnAmount);
emit Liquidated(msg.sender, user, pocketId, liquidationReward, burnAmount);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting inconsistency that occurs during the liquidation process of a borrowing protocol. When a position is liquidated, the contract correctly burns the liquidator's TCAPV2 tokens to represent repayment of the debtor's obligations, but it fails to invoke the internal routine that updates the debtor's recorded debt balance. Specifically, the modifyPosition() function, which should decrement the liquidated account's debt by the amount of tokens burned, is omitted. As a result, the debtor’s debt remains unchanged while the collateral is removed, allowing the same under‑collateralized account to be liquidated repeatedly until its collateral is exhausted. An attacker who can trigger liquidation on an under‑collateralized position can repeatedly claim liquidation rewards and cause the protocol to burn tokens without ever reducing the outstanding debt, breaking the invariant that total debt equals total minted tokens. The impact includes loss of all collateral for the affected user, phantom debt that remains on the protocol’s books, and potential over‑issuance of rewards to liquidators. This condition manifests only when the liquidation function executes the withdraw and burn steps but does not call the position‑adjusting routine; the bug was uncovered during a formal audit by Spearbit, where a test case demonstrated that after liquidation the collateral balance reported zero while the minted (debt) value stayed at its original amount. The issue is subtle because the transaction emits expected events and the token burn appears to indicate repayment, so observers may assume the debt was cleared. The recommended remediation is to ensure that the modifyPosition (or equivalent) call is performed with a negative amount equal to the burned tokens before or after the burn, thereby synchronizing the debt ledger with the token supply reduction. This class of bug belongs to state‑inconsistency or accounting‑logic errors where side‑effects on one ledger are not mirrored on another, often leading to symptoms such as “funds disappear”, “debt never repaid”, or “collateral goes to zero while loan amount stays the same”. From a user’s perspective the UI would show zero collateral but still display the original loan amount, contradicting the expectation that liquidation settles the debt, and repeated liquidations could drain the user’s assets while the protocol’s debt accounting remains inflated, violating core business logic that collateral must back outstanding debt.
