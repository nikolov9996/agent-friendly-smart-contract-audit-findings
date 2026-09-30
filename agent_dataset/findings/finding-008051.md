---
id: 8051
severity: "High"
---

# solverMetaTryCatch() assumes there is no pre-existing ETH in contract

## Description

```solidity
solverMetaTryCatch()
requires ExecutionEnvironment's balance to be the same as solverOp.value:
require(address(this).balance == solverOp.value, "ERR-CE05 IncorrectValue");
```
However, someone can frontrun this transaction and send some ETH to ExecutionEnvironment making its balance non-zero. This leads to the solverMetaTryCatch() call reverting, since the call is sent with an ETH amount equal to solverOp.value. This makes address(this).balance > solverOp.value. Since the error would be treated as SolverOutcome.EVMError in the _solverOpWrapper(), the solver would be forced to pay the gas costs for this revert.

## Proof of Concept

no poc

## Recommendation

Refactor the function as follows:
• Update ExecutionEnvironment.sol#L152 as:
```solidity
- require(address(this).balance == solverOp.value, "ERR-CE05 IncorrectValue");
+ require(msg.value == solverOp.value, "ERR-CE05 IncorrectValue");
```
• Update startBalance initialization:
```solidity
- startBalance = 0; // address(this).balance - solverOp.value;
+ startBalance = address(this).balance - msg.value;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the solverMetaTryCatch function of the ExecutionEnvironment contract. The function asserts that the contract's ETH balance exactly matches the value specified in the solver operation (solverOp.value) by using require(address(this).balance == solverOp.value, \"ERR-CE05 IncorrectValue\"). This assumption is incorrect because the contract's balance can be altered by external transactions before the solver call. An attacker can front‑run the intended transaction and send a small amount of ETH to the ExecutionEnvironment contract, causing address(this).balance to become greater than solverOp.value. When the solverMetaTryCatch call is executed, the balance check fails, the require statement reverts, and the surrounding wrapper interprets the failure as an EVMError. As a result the solver transaction is aborted and the caller must still pay the gas consumed by the revert. The impact is a denial‑of‑service style condition where legitimate solvers cannot be executed unless the contract balance is exactly the expected amount, and the gas cost is wasted. This issue affects any participant that relies on the solver execution, including protocol operators, users submitting operations, and the overall economic model of the system. The problem was discovered during a manual security audit that examined the logic of value handling and identified that the balance check does not consider pre‑existing ETH. The bug is subtle because checking the contract balance is a common pattern and may appear correct in isolation; however, it ignores the possibility of external deposits and front‑running. The vulnerability belongs to the class of improper balance verification or value‑dependency bugs, where contract state is assumed to be immutable between calls. From a user perspective the transaction simply fails with an \"IncorrectValue\" error, no funds are transferred, and the UI may show that the operation did not complete while the user's ETH balance is reduced only by the gas fee. To remediate the issue the code should compare the amount of ETH sent with the operation (msg.value) rather than the contract's total balance, and the internal accounting of startBalance should be derived from address(this).balance minus msg.value. This change eliminates the reliance on a mutable contract balance and prevents front‑run attacks that inject extra ETH.
