---
id: 21977
severity: "High"
---

# Impossible to liquidate borrower when a `TroveManager` instance only has 1 active borrower

## Description

When a `TroveManager` instance only has 1 active borrower it is impossible to liquidate that borrower since `LiquidationManager::liquidateTroves` only executes code within the [while](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L166) loop and [if](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L192) statement when `troveCount > 1`:
```solidity
uint256 troveCount = troveManager.getTroveOwnersCount();
...
while (trovesRemaining > 0 && troveCount > 1) {
...
if (trovesRemaining > 0 && !troveManagerValues.sunsetting && troveCount > 1) {
```
Because the code inside the `while` loop and `if` statement never gets executed, `totals.totalDebtInSequence` is never set to a value which results in this [revert](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L230):
```solidity
require(totals.totalDebtInSequence > 0, "TroveManager: nothing to liquidate");
```
The same problem applies to `LiquidationManager::batchLiquidateTroves` which has a similar [while](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L287) loop and [if](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L314) statement condition:
```solidity
uint256 troveCount = troveManager.getTroveOwnersCount();
...
while (troveIter < length && troveCount > 1) {
...
if (troveIter < length && troveCount > 1) {
```
And [reverts](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L360) with the same error:
```solidity
require(totals.totalDebtInSequence > 0, "TroveManager: nothing to liquidate");
```
It is impossible to liquidate a borrower when a `TroveManager` instance only has 1 active borrower. The borrower can be liquidated once other borrowers become active on the same `TroveManager` instance but this can result in late liquidation with loss of funds to the protocol.
Additionally it is permanently impossible to liquidate the last active borrower in a `TroveManager` that is sunsetting, since in that case no new active borrowers can be created.

## Proof of Concept

Add the following PoC contract to `test/foundry/core/LiquidationManagerTest.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

// test setup
import {BorrowerOperationsTest} from "./BorrowerOperationsTest.t.sol";

contract LiquidationManagerTest is BorrowerOperationsTest {

    function setUp() public virtual override {
        super.setUp();

        // verify staked btc trove manager enabled for liquidation
        assertTrue(liquidationMgr.isTroveManagerEnabled(stakedBTCTroveMgr));
    }

    function test_impossibleToLiquidateSingleBorrower() external {
        // depositing 2 BTC collateral (price = $60,000 in MockOracle)
        // use this test to experiment with different hard-coded values
        uint256 collateralAmount = 2e18;

        uint256 debtAmountMax
            = (collateralAmount * _getScaledOraclePrice() / borrowerOps.CCR())
              - INIT_GAS_COMPENSATION;

        _openTrove(users.user1, collateralAmount, debtAmountMax);

        // set new value of btc to $1 which should ensure liquidation
        mockOracle.setResponse(mockOracle.roundId() + 1,
                               int256(1 * 10 ** 8),
                               block.timestamp + 1,
                               block.timestamp + 1,
                               mockOracle.answeredInRound() + 1);
        // warp time to prevent cached price being used
        vm.warp(block.timestamp + 1);

        // then liquidate the user - but it fails since the
        // `while` and `for` loops get bypassed when there is
        // only 1 active borrower!
        vm.expectRevert("LiquidationManager: nothing to liquidate");
        liquidationMgr.liquidate(stakedBTCTroveMgr, users.user1);

        // attempting to use the other liquidation function has same problem
        uint256 mcr = stakedBTCTroveMgr.MCR();
        vm.expectRevert("LiquidationManager: nothing to liquidate");
        liquidationMgr.liquidateTroves(stakedBTCTroveMgr, 1, mcr);

        // the borrower is impossible to liquidate
    }
}
```
Run with `forge test --match-test test_impossibleToLiquidateSingleBorrower`.

## Recommendation

Simply changing `troveCount >= 1` results in a panic divide by zero inside `TroveManager::_redistributeDebtAndColl`. A possible solution is to add the following in that function:
```diff
        uint256 totalStakesCached = totalStakes;

+       // if there is only 1 trove open and that is being liquidated, prevent
+       // a panic during liquidation due to divide by zero
+       if(totalStakesCached == 0) {
+           totalStakesCached = 1;
+       }

        // Get the per-unit-staked terms
```
With this change it appears safe to enable `troveCount >= 1` everywhere but inside `LiquidationManager::liquidateTroves` there is some code that [looks for other troves](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/LiquidationManager.sol#L196-L205) which may cause problems if executing when only 1 Trove exists.
Note: in the existing code there is this [comment](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/TroveManager.sol#L1083-L1086) which indicates that "liquidating the final trove" is blocked to allow a `TroveManager` being sunset to be closed. But the current implementation prevents liquidation of any single trove at any time.
The suggested fix may prevent a sunsetting `TroveManager` from being closed if the last trove is liquidated since this would result in a state where `defaultedDebt > 0` and hence `TroveManager::getEntireSystemDebt` would return > 0 which causes this [check](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/core/BorrowerOperations.sol#L124) to return false.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an edge‑case logic error in the liquidation flow of the TroveManager/LiquidationManager pair. When a TroveManager instance contains exactly one active borrower, the liquidation functions liquidateTroves and batchLiquidateTroves skip their core processing because both the while loop and the subsequent if statement are guarded by the condition troveCount > 1. As a result the internal variable totals.totalDebtInSequence is never populated and the function reverts with the message "TroveManager: nothing to liquidate". The same guard exists in the batch version, leading to identical failure. Consequently a borrower that becomes under‑collateralised (for example after a price drop) cannot be liquidated as long as it is the sole active trove, and the protocol is unable to recover the collateral or offset the debt. This problem also persists when the TroveManager is in a sunsetting state, where no new borrowers can be added, making the final trove permanently immune to liquidation. The impact is that the protocol may retain unsafe debt, potentially causing loss of funds for lenders and undermining the economic guarantees of the system. The issue was discovered during a formal audit by Cyfrin, which added a targeted test that opened a single trove, forced a price crash and observed the expected revert. The bug is hard to notice because normal operation usually involves many borrowers, so the single‑borrower path is rarely exercised in standard tests. To fix the issue the liquidation guard must be relaxed to troveCount >= 1 and the redistribution routine must be protected against a divide‑by‑zero when totalStakes is zero. Adding a safe‑guard in _redistributeDebtAndColl that treats a zero‑stake situation as a special case prevents the panic while still allowing the final trove to be liquidated. In summary, the contract incorrectly assumes that at least two troves exist before performing liquidation, which blocks the liquidation of the last active borrower, leading to stuck collateral, failed liquidation transactions, and potential protocol insolvency.
