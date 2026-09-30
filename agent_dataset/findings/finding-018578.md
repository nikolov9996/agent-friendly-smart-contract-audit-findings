---
id: 18578
severity: "High"
---

# The difference between `gasLeft` and `gasAfterTransfer` is greater than `TRANSFER_OVERHEAD`, causing `anyExecute` to always fail

## Description

```solidity
///Save gas left
uint256 gasLeft = gasleft();
.
.
. 
.
//Transfer gas remaining to recipient
SafeTransferLib.safeTransferETH(_recipient, gasRemaining - minExecCost);
//Save Gas
uint256 gasAfterTransfer = gasleft();
//Check if sufficient balance
if (gasLeft - gasAfterTransfer > TRANSFER_OVERHEAD) {
    _forceRevert();
    return;
}
```
It checks if the difference between `gasLeft` and `gasAfterTransfer` is greater than `TRANSFER_OVERHEAD`. Then, it calls `_forceRevert()` so that `Anycall Executor` reverts the call. This check has been introduced to prevent any arbitrary code executed in the `_recipient's fallback` (this was confirmed by the sponsor). However, the condition `gasLeft - gasAfterTransfer > TRANSFER_OVERHEAD` is always true. `TRANSFER_OVERHEAD` is `24_000`.

```solidity
uint256 internal constant TRANSFER_OVERHEAD = 24_000;
```

And the **gas spent between `gasLeft` and `gasAfterTransfer` is nearly `70_000` which is higher than `24_000`**. Thus, causing the function to always revert. Function `_payExecutionGas` is called by `anyExecute` which is called by the `Anycall Executor`. This means `anyExecute` will also fail. This happens because the `gasLeft` value is stored before replenishing gas and not before the transfer.

## Proof of Concept

This PoC is independent from the codebase (but uses the same code). There is one contract simulating `BranchBridgeAgent.anyExecute`.

When we run the test, `anyExecute` will revert because `gasLeft - gasAfterTransfer` is always greater than `TRANSFER_OVERHEAD` (`24_000`).

Here is the output of the test:
```solidity
[PASS] test_anyexecute_always_revert_bc_transfer_overhead() (gas: 124174)
Logs:
  (gasLeft - gasAfterTransfer > TRANSFER_OVERHEAD) => true
  gasLeft - gasAfterTransfer = 999999999999979606 - 999999999999909238 = 70368

Test result: ok. 1 passed; 0 failed; finished in 1.88ms
```

## Recommendation

Increase the `TRANSFER_OVERHEAD` to cover the actual gas spent. You could also add a gas checkpoint immediately before the transfer to make the naming makes sense (i.e. `TRANSFER_OVERHEAD`). However, the gas will be nearly `34_378`, which is still higher than `TRANSFER_OVERHEAD` (`24_000`).

You can simply comment out the code after `gasLeft` till the transfer, by removing `_minExecCost` from the value to transfer since it is commented out. Now, when you run the test again, you will see an output like this (with a failed test but we are not interested in it anyway):
```solidity
[FAIL. Reason: Call did not revert as expected] test_anyexecute_always_revert_bc_transfer_overhead() (gas: 111185)
Logs:
  (gasLeft - gasAfterTransfer > TRANSFER_OVERHEAD) => true
  gasLeft - gasAfterTransfer = 999999999999979606 - 999999999999945228 = 34378

Test result: FAILED. 0 passed; 1 failed; finished in 1.26ms
```

**`gasLeft` - `gasAfterTransfer` = 34378**

Please note that I have tested a simple function in Remix as well and it gave the same gas spent (i.e. 34378):
```solidity
// copy the library code from Solady and paste it here
// https://github.com/Vectorized/solady/blob/main/src/utils/SafeTransferLib.sol

contract Test {

       function testGas() payable public returns (uint256){
        ///Save gas left
        uint256 gasLeft = gasleft();

        //Transfer gas remaining to recipient
        SafeTransferLib.safeTransferETH(address(0), 1 ether);

        //Save Gas
        uint256 gasAfterTransfer = gasleft();

        return gasLeft-gasAfterTransfer;

       }

}
```
The returned value will be 34378.

We recognize the audit’s findings on Anycall Gas Management. These will not be rectified due to the upcoming migration of this section to LayerZero.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect gas accounting check inside the Anycall executor’s anyExecute flow. The contract records the amount of gas available before performing a safe ETH transfer to the recipient and stores it in a variable called gasLeft. After the transfer, it records the remaining gas in gasAfterTransfer and then compares the difference to a constant named TRANSFER_OVERHEAD, which is set to 24000. Because the transfer operation consumes roughly 34000 to 70000 gas, the expression gasLeft - gasAfterTransfer > TRANSFER_OVERHEAD evaluates to true on every execution. When the condition is true the code deliberately calls _forceRevert, causing the Anycall executor to revert the entire anyExecute call. As a result, any cross‑chain call that relies on anyExecute is forced to fail, preventing the intended logic from running and potentially locking funds or breaking protocol workflows. The issue occurs every time the function _payExecutionGas is invoked, which is a mandatory step in the anyExecute path, so the failure is deterministic under normal network conditions. The bug was discovered during a formal audit and reproduced with a unit test that measured the gas delta and observed the constant being exceeded. It is subtle because the constant value appears reasonable and the gas consumption of a low‑level transfer is not obvious from the source code, making the always‑true condition easy to miss during code review. The impact is high: legitimate users expecting a successful cross‑chain execution receive no result, may see their balances unchanged while the call reverts, and the protocol cannot guarantee delivery of messages. To remediate the issue the gas checkpoint should be taken after the transfer or the constant should be increased to cover the actual overhead, or the entire sanity check should be removed if it no longer serves its original purpose. In essence, the bug is a classic example of an inaccurate gas‑usage guard that unintentionally blocks execution, violating the business assumption that the executor will only revert when the recipient’s fallback consumes excessive gas.
