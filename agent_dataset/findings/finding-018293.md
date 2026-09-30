---
id: 18293
severity: "High"
---

# KangarooVault `QueuedWithdraw` Denial of Service

## Description

When the `KangarooVault` has an open position, any withdrawals that are initiated, are queued.

`QueuedWithdrawals` work in two steps.

  1. A user initialtes the Withdrawal via `initiateWithdrawal` (`KangarooVault.sol#L215`). This burns the `VaultToken` and `if (positionData.positionId != 0)` (`KangarooVault.sol#L225`) adds the request to the `withdrawalQueue`.
  2. `processWithdrawalQueue()` can be called to process requests in the `withdrawalQueue` that have passed `minWithdrawDelay` to transfer the SUSD tokens to the user.

If the processing of a `QueuedWithdraw` entry in the `withdrawalQueue` reverts, the `queuedWithdrawalHead` (`KangarooVault.sol#L331`) will never increase and further processing of the queue will be impossible. This means that any users that have placed a QueuedWithdraw after the reverting entry will have lost their vaultToken without receiving their SUSD.

## Proof of Concept

When calling the `initiateWithdrawal()` function, the user can provide an address of the receiver of funds.

When processing the withdrawal queue, the contracts does all the required checks, and then transfers the SUSD (`KangarooVault.sol#L322`) to the provided user.

If we look at the [Synthetix sUSD token](https://optimistic.etherscan.io/address/0x8c6f28f2F1A3C87F0f938b96d27520d9751ec8d9) and it’s [target implementation](https://optimistic.etherscan.io/address/0xdfa2d3a0d32f870d87f8a0d7aa6b9cdeb7bc5adb#code) we will find that the SUSD token transfer code is:

[sUSD MultiCollateralSynth:L723-L739](https://optimistic.etherscan.io/address/0xdfa2d3a0d32f870d87f8a0d7aa6b9cdeb7bc5adb#code)

```solidity
function _internalTransfer(
    address from,
    address to,
    uint value
) internal returns (bool) {
    /* Disallow transfers to irretrievable-addresses. */
    require(to != address(0) && to != address(this) && to != address(proxy), "Cannot transfer to this address");

    // Insufficient balance will be handled by the safe subtraction.
    tokenState.setBalanceOf(from, tokenState.balanceOf(from).sub(value));
    tokenState.setBalanceOf(to, tokenState.balanceOf(to).add(value));

    // Emit a standard ERC20 transfer event
    emitTransfer(from, to, value);

    return true;
}
```

This means any SUSD transfer to the SUSD proxy or implementation contract, will result in a revert.

An attacker can use this to make a `initiateWithdrawal()` request with `user=sUSDproxy` or `user=sUSD_MultiCollateralSynth`. Any user that request a Withdrawal via `initiateWithdrawal()` after this, will lose their vault tokens without receiving their SUSD.

The attacker can do this at any time, or by frontrunning a specific (large) `initiateWithdrawal()` request.

To test it, a check is added to the mock contract that is used for SUSD in the test scripts:

```diff
diff --git a/src/test-helpers/MockERC20Fail.sol b/src/test-helpers/MockERC20Fail.sol
index e987f04..1ce10ec 100644
--- a/src/test-helpers/MockERC20Fail.sol
+++ b/src/test-helpers/MockERC20Fail.sol
@@ -18,6 +18,9 @@ contract MockERC20Fail is MockERC20 {
     }

     function transfer(address receiver, uint256 amount) public override returns (bool) {
+
+        require(receiver != address(0xDfA2d3a0d32F870D87f8A0d7AA6b9CdEB7bc5AdB) , "Cannot transfer to this address");
+
         if (forceFail) {
             return false;
         }
```

In the `KangarooVault.t.sol` test script, the following test was added to demonstrated the issue:

```solidity
// add to top of file:
import {IVaultToken} from "../../src/interfaces/IVaultToken.sol";

// add to KangarooTest Contract:
function testWithdrawalDOS() public {

    IVaultToken vault_token = kangaroo.VAULT_TOKEN();
    // make deposit for user_2
    susd.mint(user_2, 2e23);
    vm.startPrank(user_2);
    susd.approve(address(kangaroo), 2e23);
    kangaroo.initiateDeposit(user_2, 2e23);
    assertEq(vault_token.balanceOf(user_2),2e23);
    vm.stopPrank();

    // have vault open a position to force queued wthdrawals
    testOpen();

    // vault has  position opened, withdrawal will be queued, vault_token burned, no USDC received
    vm.startPrank(user_2);
    kangaroo.initiateWithdrawal(user_2, 1e23);
    assertEq(susd.balanceOf(user_2),0);
    assertEq(vault_token.balanceOf(user_2),1e23);
    
    // process withdrawalqueue, withdrawam should pass
    skip(kangaroo.minWithdrawDelay());         
    kangaroo.processWithdrawalQueue(3);
    uint256 user_2_balance = susd.balanceOf(user_2);
    assertGt(user_2_balance,0);        
    vm.stopPrank();

    // user 3 frontruns with fake/reverting withdrawal request.
    // to 0xDfA2d3a0d32F870D87f8A0d7AA6b9CdEB7bc5AdB (= SUSD MultiCollateralSynth contract address). 
    // This will cause SUSD transfer to revert.
    vm.startPrank(user_3);        
    kangaroo.initiateWithdrawal(0xDfA2d3a0d32F870D87f8A0d7AA6b9CdEB7bc5AdB, 0);
    vm.stopPrank();

    // user_2 adds another withdrawal request, after the attackers request, vault_token burned, no USDC received
    vm.startPrank(user_2);  
    kangaroo.initiateWithdrawal(user_2, 1e23);
    assertEq(vault_token.balanceOf(user_2),0);

    // processWithdrawalQueue now reverts and no funds received
    skip(kangaroo.minWithdrawDelay());
    vm.expectRevert(bytes("TRANSFER_FAILED"));
    kangaroo.processWithdrawalQueue(3);
    assertEq(susd.balanceOf(user_2),user_2_balance);
    assertEq(vault_token.balanceOf(user_2),0);
    vm.stopPrank();

}
```

## Recommendation

The processing of `withdrawalQueue` should have a mechanism to handle reverting `QueuedWithdraw` entries. Either by skipping them and/or moving them to another `failedWithdrawals` queue.

Similar but different from <https://github.com/code-423n4/2023-03-polynomial-findings/issues/103>

Somehow the import should be `import {IVaultToken} from "../src/interfaces/IVaultToken.sol";` (one step less), but the POC runs correctly after that.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition in the withdrawal mechanism of the KangarooVault contract. When the vault holds an open trading position, user withdrawals are not executed immediately but are placed into a FIFO withdrawalQueue. Each entry records the address that should receive the underlying SUSD tokens. The contract processes the queue via processWithdrawalQueue, advancing a pointer called queuedWithdrawalHead only after a successful transfer. The root cause is that the processing logic does not handle a transfer that reverts; it simply aborts, leaving queuedWithdrawalHead unchanged. Because the SUSD token contract deliberately reverts when the destination address is the token’s own proxy or implementation contract, an attacker can craft a withdrawal request that specifies one of those prohibited addresses. When processWithdrawalQueue reaches this malicious entry, the internal SUSD transfer throws, the function reverts, and the head pointer never moves past the failing entry. Consequently every subsequent queued withdrawal – even legitimate ones – remains stuck: the user’s vault tokens are burned at initiation, but no SUSD is ever transferred. From a user’s perspective the symptom is that after initiating a withdrawal they see their vault token balance reduced to zero while their SUSD balance stays unchanged, and later attempts to process the queue result in a “TRANSFER_FAILED” error. The impact is loss of access to funds for any user whose request follows the malicious entry, effectively a denial of service for withdrawals and a potential financial loss if the vault token cannot be reclaimed. The condition only manifests when the vault has an open position (which forces queuing) and when a queued entry points to a prohibited address; otherwise withdrawals work as expected. The issue was discovered during a formal audit by reproducing the failure with a mock ERC20 that forces a revert on transfers to the prohibited address, and confirming that the queue head never advances. It is hard to notice because the contract behaves correctly until the specific malicious entry is processed, at which point the whole queue silently stops. The proper mitigation is to make the queue processing resilient: catch transfer failures, skip the offending entry, optionally record it in a separate failedWithdrawals list, and always advance the head pointer so that later legitimate withdrawals can continue. This transforms the bug from a single‑point failure into a recoverable condition and restores the intended accounting guarantees of the vault.
