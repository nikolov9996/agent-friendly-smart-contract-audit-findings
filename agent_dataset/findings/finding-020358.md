---
id: 20358
severity: "High"
---

# It is possible to frontrun liquidations with self

## Description

Borrower.warn sets the time when the liquidation (involving swap) can happen:
```solidity
slot0 = slot0_ | ((block.timestamp + LIQUIDATION_GRACE_PERIOD) << 208);
```
But Borrower.liquidation clears the warning regardless of whether account is healthy or not after the repayment:
```solidity
_repay(repayable0, repayable1);
slot0 = (slot0_ & SLOT0_MASK_POSITIONS) | SLOT0_DIRT;
```
Very important protocol function (liquidation) can be DOS'ed and make the unhealthy accounts avoid liquidations for a very long time. Malicious users can thus open huge risky positions which will then go into bad debt causing loss of funds for all protocol users as they will not be able to withdraw their funds and can cause a bank run - first users will be able to withdraw, but later users won't be able to withdraw as protocol won't have enough funds for this.

## Proof of Concept

The scenario above is demonstrated in the test, add this to Liquidator.t.sol:
```solidity
function test_liquidationFrontrun() public {
    uint256 margin0 = 1595e18;
    uint256 margin1 = 0;
    uint256 borrows0 = 0;
    uint256 borrows1 = 1e18 * 100;
    // Extra due to rounding up in liabilities
    margin0 += 1;
    deal(address(asset0), address(account), margin0);
    deal(address(asset1), address(account), margin1);
    bytes memory data = abi.encode(Action.BORROW, borrows0, borrows1);
    account.modify(this, data, (1 << 32));
    assertEq(lender0.borrowBalance(address(account)), borrows0);
    assertEq(lender1.borrowBalance(address(account)), borrows1);
    assertEq(asset0.balanceOf(address(account)), borrows0 + margin0);
    assertEq(asset1.balanceOf(address(account)), borrows1 + margin1);
    _setInterest(lender0, 10100);
    _setInterest(lender1, 10100);
    account.warn((1 << 32));
    uint40 unleashLiquidationTime = uint40((account.slot0() >> 208) % (1 << 40));
    assertEq(unleashLiquidationTime, block.timestamp + LIQUIDATION_GRACE_PERIOD);
    skip(LIQUIDATION_GRACE_PERIOD + 1);
    // listen for liquidation, or be the 1st in the block when warning is cleared
    // liquidate with very high strain, basically keeping the position, but
    // clearing the warning
    account.liquidate(this, bytes(""), 1e10, (1 << 32));
    unleashLiquidationTime = uint40((account.slot0() >> 208) % (1 << 40));
    assertEq(unleashLiquidationTime, 0);
    // the liquidation command we've frontrun will now revert (due to warning
    // not set: "Aloe: grace")
    vm.expectRevert();
    account.liquidate(this, bytes(""), 1, (1 << 32));
}
```

## Recommendation

Consider clearing "warn" status only if account is healthy after liquidation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that the liquidation routine clears the warning flag unconditionally after performing a repayment, even if the account remains under‑collateralized. Borrower.warn stores a timestamp indicating when the grace period expires by encoding block.timestamp + LIQUIDATION_GRACE_PERIOD into slot0. Borrower.liquidate calls an internal _repay and then overwrites the warning bits with SLOT0_DIRT without checking the post‑repayment health of the account. As a result an attacker can trigger a liquidation transaction that repays only a tiny amount, clears the warning, and then let the block finish. Any subsequent liquidation attempt in the same block or after the grace period will find the warning cleared and revert with the “Aloe: grace” error, effectively denying liquidation of an unhealthy position. This front‑running attack creates a denial‑of‑service condition: the protocol cannot liquidate risky accounts, allowing borrowers to accumulate large bad‑debt positions. When the warning is missing, users attempting to withdraw may see their balances stuck or receive no funds, and the protocol may run out of liquidity, leading to a potential bank run where early withdrawers are paid but later ones receive nothing. The issue was discovered during an audit by constructing a test that calls warn, skips the grace period, then calls liquidate with an exaggerated strain parameter to clear the warning and verifies that a second liquidation reverts. The bug is subtle because the warning flag is intended only as a timing guard, and developers may assume it is cleared only after a successful liquidation; the unconditional clearing violates that expectation. The class of bug is an improper state transition that enables a race condition and front‑running, a form of denial‑of‑service through state flag manipulation. To remediate, the contract should only clear the warning flag if the account is healthy after the repayment, or defer clearing until a successful liquidation has been confirmed, thereby preserving the grace‑period guard and preventing the front‑run attack.
