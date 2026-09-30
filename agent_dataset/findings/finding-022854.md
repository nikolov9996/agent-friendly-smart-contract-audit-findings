---
id: 22854
severity: "Medium"
---

# Signature hash is wrongly computed and leads

## Description

The current approach to computing the hash to be signed does not properly encode EIP191’s validator address, leading to properly signed EIP-191 signatures being rejected by the wallet. Telcoin Wallet incorporates the execute and transferERC20 functions, both of which require a specific hash to be signed by at least one gatekeeper and an additional gatekeeper or owner. The hash to be signed is specific to each of the functions, and is computed given the calldata passed when calling the function. However, the standard to follow for the hash to sign is EIP-191 with 0x00 version (Data with intended validator), which expects the following format to be signed:
• EIP-191 prefix (0x19).
• Version of EIP-191 signature (0x00 in Telcoin’s case, corresponding to “Data with intended validator” ).
• Intended validator address (a 20-byte field set to address(this)).
• Data to sign. As per the EIP, “The data to sign could be any arbitrary data”. field holding data corresponding to an address left-padded with zeroes. Because of this, if one was to build a hash following EIP-191 using plain solidity, the encoding won’t pad the validator address with zeroes, and instead of using abi.encode, which would incorrectly pad validator with 12 zeroes on the left):
```solidity
function toDataWithIntendedValidator(address validator, bytes memory dataToSign)
    internal pure returns (bytes32) {
    return keccak256(abi.encodePacked("\x19\x00", validator, dataToSign));
}
```
Telcoin attempts to perform an operation similar to toDataWithIntendedValidator using plain assembly. In order to build the hash to be signed, execute will store the data to be hashed in memory so that later it can be hashed using the keccak256 opcode. The memory layout chosen by Telcoin to hash the data is the following:
• 0x80-0x81: EIP-191 prefix (0x19).
• 0x81-0x82: 0x00 (version of EIP-191 signature). is used in order to store this data, so the address will be stored left-padded with zeroes from byte 0x82 to byte 0xa2 in memory, where bytes from 0x82 to 0x1e correspond to the padding zeroes, and bytes from 0x1e to 0xa2 correspond to the actual address. This is wrong, as EIP-191 does not expect the validator address to be zero-padded.
• 0xa2-onwards: Actual data to sign.
```solidity
// TelcoinWallet.sol
function execute() {
    // Set up EIP191 prefix.
    mstore8(0x80, 0x19)
    mstore8(0x81, 0x00)
    mstore(0x82, address())
    // Copy method signature + _identifier + _destination + _value to memory.
    calldatacopy(0xa2, 0, 0x64)
    // Copy _data (without offset or length) after that.
    calldatacopy(0x106, 0x164, _dataLength)
    // Hash all user data except the signatures.
    //
    // The second argument cannot overflow due to an
    // earlier check limiting the maximum value of the
    // length variable.
    let hash := keccak256(0x80, add(0x86, _dataLength))
}
```
As mentioned, the main problem is that the current approach followed by Telcoin will add padding to the address stored, so the hash computed will be calculated as if abi.encode was used, instead of abi.encodePacked. Medium. Valid EIP-191 signatures will be rejected by the code, making transactions that should be accepted to always fail.

## Proof of Concept

The following proof of concept shows how data is improperly encoded with an example. Let’s say we wanted to hash the following data:
• EIP-191 prefix (0x19).
• 0x00 (version of EIP-191 signature).
• 0x82-0xa2: Address of validator, for this example it will be 0x7c8999dc9a822c1f0df42023113edb4fdd543266
• Data to sign:
– Signature of the execute function (0x9d55b53f)
– Identifier, with value 1157920892373161954235694525131470419644116263186134137302739652687910
– A destination with address 0x5615dEB798BB3E4dFa0139dFa1b3D433Cc23b72f
– A value of 1 ether
– Empty calldata
With this data, the expected calldata to be signed would be the following: 0x19005615deb798bb3e4dfa0139dfa1b3d433cc23b72f9d55b53ffffffffffffffffffff000000000000 added 12-byte zero padding between the 0x1900 prefix and the start of the wallet’s address 0x5615...) 0x19000000000000000000000000005615deb798bb3e4dfa0139dfa1b3d433cc23b72f9d55b5 Let’s dissect it:
• 0x1900 —> the 0x1900 prefix
• 0000000000000000000000005615deb798bb3e4dfa0139dfa1b3d433cc23b72 —> the validator address (incorrectly padded with 12 bytes on the left)
• f9d55b53 —> the execute selector
• ffffffffffffffffffff00000000000000000000000000000000000000400010 —> The identifier
• 00000000000000000000000007c8999dc9a822c1f0df42023113edb4fdd54326 —> The destination address
• 60000000000000000000000000000000000000000000000000de0b6b3a764000 —> The 1 ETH value, encoded in hex
• 0 —> The dynamic data (was set to empty)
This calldata can be obtained by adding the following computeDataToHash function to TelcoinWallet, which performs the exact same computations to calculate the hash in execute, and serves as a helper to visualize the calldata returned:
```solidity
// TelcoinWallet.sol
case 0xc19d93fb /* bytes4(keccak256("state()")) */ {
    state()
    stop()
}
case 0x56bdcd27 { /* computeDataToHash(uint256,address,uint256,bytes,uint8,bytes32,bytes32,uint8,bytes32,bytes32) */
    computeDataToHash() <---- add this case
    stop()
}
default {
    // We stop the transaction here and accept any ETH that was passed in.
    stop()
}
function computeDataToHash() { <---- add this function
    let _dataLength := calldataload(0x144)
    // Set up EIP191 prefix.
    mstore8(0x80, 0x19)
    mstore8(0x81, 0x00)
    mstore(0x82, address())
    // Copy method signature + _identifier + _destination + _value to memory.
    mstore8(0xa2, 0x9d)
    mstore8(0xa3, 0x55)
    mstore8(0xa4, 0xb5)
    mstore8(0xa5, 0x3f)
    calldatacopy(0xa6, 0x04, 0x60)
    // Copy _data (without offset or length) after that.
    calldatacopy(0x106, 0x164, _dataLength)
    return(0x80, add(0x86, _dataLength))
}
```
Then, create a foundry project with the TelcoinWallet source file and paste the following test:
```solidity
// TestPoc.t.sol
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;
import "forge-std/Test.sol";
import "../src/TelcoinWallet.sol";
import "forge-std/console.sol";
interface ITelcoinWallet {
    function transferErc20(
        uint256,
        address,
        address,
        uint256,
        uint256,
        address,
        uint256,
        uint256,
        address,
        uint8,
        bytes32,
        bytes32,
        uint8,
        bytes32,
        bytes32,
        uint8,
        bytes32,
        bytes32
    ) external;
    function execute(
        uint256,
        address,
        uint256,
        bytes calldata,
        uint8,
        bytes32,
        bytes32,
        uint8,
        bytes32,
        bytes32
    ) external;
    function addOwner(address) external;
    function removeOwner(address) external;
    function replaceGatekeeper(address, address) external;
    function initialize(uint256, address, address, address) external;
    function isOwner(address) external view returns (bool);
    function state() external;
}
contract ContractTest is Test {
    ITelcoinWallet public wallet;
    uint256 public currState;
    address public gatekeeperA;
    address public gatekeeperB;
    address public owner;
    uint256 public gatekeeperAPrivKey;
    uint256 public gatekeeperBPrivKey;
    uint256 public ownerPrivKey;
    function setUp() public {
        wallet = ITelcoinWallet(address(new TelcoinWallet()));
        assembly {
            sstore(currState.slot, shl(180, not(0)))
        }
        (gatekeeperA, gatekeeperAPrivKey) = makeAddrAndKey("gatekeeperA");
        (gatekeeperB, gatekeeperBPrivKey) = makeAddrAndKey("gatekeeperB");
        (owner, ownerPrivKey) = makeAddrAndKey("owner");
        // Initialize wallet
        wallet.initialize(currState, gatekeeperA, gatekeeperB, owner);
        assertFalse(wallet.isOwner(gatekeeperA));
        assertFalse(wallet.isOwner(gatekeeperB));
        assertTrue(wallet.isOwner(address(0xaa)));
        assertTrue(wallet.isOwner(owner));
    }
    function testWrongEIP191Implementation() external {
        uint256 identifier;
        assembly {
            identifier := add(identifier, shl(8, 1)) // set nonce
            identifier := add(identifier, shl(26, timestamp())) // set timestamp
            identifier := add(sload(currState.slot), identifier) // add to current identifier
        }
        (, bytes memory dataToHash) = address(wallet).call(
            abi.encodeWithSignature(
                "computeDataToHash(uint256,address,uint256,bytes,uint8,bytes32,bytes32,uint8,bytes32,bytes32)",
                identifier,
                owner,
                1 ether,
                ""
            )
        );
        console.logBytes(dataToHash);
    }
}
```
As we can see, the validator address is wrongly padded with 12 zero bytes, which breaks EIP-191 compatibility.

## Recommendation

When encoding the validator address, perform the following change:
```solidity
function execute() {
    // When executing this function, the calldata is intended to be:
    //
    // start | description               | length in bytes
    // --------+-------------------------------+------------------
    // 0x00    | Method signature          | 0x4
    // 0x04    | _identifier               | 0x20
    // 0x24    | _destination              | 0x20
    // 0x44    | _value                    | 0x20
    // 0x64    | _dataOffset               | 0x20
    // 0x84    | _sig1V                    | 0x20
    // 0xa4    | _sig1R                    | 0x20
    // 0xc4    | _sig1S                    | 0x20
    // 0xe4    | _sig2V                    | 0x20
    // 0x104   | _sig2R                    | 0x20
    // 0x124   | _sig2S                    | 0x20
    // 0x144   | _dataLength               | 0x20
    // 0x164   | _data                     | _dataLength
    //
    // We will copy these in memory using the following layout:
    //
    // start | description               | length in bytes
    // --------+-------------------------------+------------------
    // 0x00    | Scratch space for __ecrecover | 0x80
    // 0x80    | EIP191 prefix 0x1900      | 0x2
    // 0x82    | EIP191 address            | 0x20
    // 0x76    | EIP191 address            | 0x20
    // 0xa2    | _methodSignature          | 0x4
    // 0xa6    | _identifier               | 0x20
    // 0xc6    | _destination              | 0x20
    // 0xe6    | _value                    | 0x20
    // 0x106   | _data                     | _dataLength
    //
    // This memory layout is set up so that we can hash all the operation data directly.
    //
    // signed
    // for execute() cannot be used for transferErc20(), or the opposite.
    //
    // signed
    // for this wallet cannot be applied to another wallet that would happen to have the
    // same owners/gatekeepers.
    // Set up EIP191 prefix.
    mstore(0x82, address())
    mstore8(0x80, 0x19)
    mstore8(0x81, 0x00)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect construction of the EIP‑191 signed message used by the Telcoin wallet’s execute and transferERC20 functions. According to EIP‑191 version 0x00, the data to be signed must consist of the 0x19 prefix, a single byte version field (0x00), the intended validator address encoded as a raw 20‑byte value, and the arbitrary payload. The contract, however, builds this message in assembly by writing the validator address with a full 32‑byte store (mstore), which left‑pads the address with twelve zero bytes. This padding changes the byte sequence that is hashed with keccak256, so the resulting hash does not match the hash that a correctly generated EIP‑191 signature expects. Consequently, signatures that are mathematically valid for the intended payload are rejected by the contract’s verification step. The flaw manifests whenever a user attempts to submit a transaction that requires a gatekeeper or owner signature – essentially any call to execute or transferERC20 – because the contract always computes a mismatched hash. From the user’s perspective the transaction simply fails with an “invalid signature” error, the expected state change (such as a token transfer or ether withdrawal) never occurs, and balances appear unchanged. The issue was discovered during a manual audit when the auditor compared the on‑chain hash computation with the EIP‑191 specification and noticed the extra zero padding. It is easy to miss because the assembly code looks superficially correct and the padding does not affect the visual layout of the address, yet it subtly violates the encoding rules. The bug does not directly enable theft; instead it creates a denial‑of‑service condition where legitimate operations cannot be performed, potentially leading to funds being locked if users cannot resend a correctly signed transaction. The proper fix is to encode the validator address without left padding, for example by using abi.encodePacked for the prefix, version, address and payload, or by adjusting the assembly to store only the 20‑byte address (e.g., using mstore8 for each byte or copying the address into memory without extra zeros). This aligns the computed hash with the EIP‑191 standard, allowing valid signatures to be accepted and restoring the intended functionality of the wallet.
