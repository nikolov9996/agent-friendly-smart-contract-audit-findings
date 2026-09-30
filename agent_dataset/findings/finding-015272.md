---
id: 15272
severity: "High"
---

# Incorrect placement of ERC7579 modeSelector

## Description

In the ERC7579 spec, we define the execution mode as follows:
callType (1 byte): 0x00 for a single call, 0x01 for a batch call, 0xfe for staticcall and 0xff for delegatecall
execType (1 byte): 0x00 for executions that revert on failure, 0x01 for executions that do not revert on failure but implement some form of error handling
unused (4 bytes): this range is reserved for future standardization
modeSelector (4 bytes): an additional mode selector that can be used to create further execution modes
modePayload (22 bytes): additional data to be passed
However, in LibERC7579, we do not correctly follow this specified order, instead encoding and decoding the modeSelector before the unused bytes. We can see this in encodeMode:
```solidity
function encodeMode(bytes1 callType, bytes1 execType, bytes4 selector, bytes22 payload)
    internal
    pure
    returns (bytes32 result)
{
    /// @solidity memory-safe-assembly
    assembly {
        mstore(0x00, callType)
        mstore(0x01, execType)
        // @audit selector should come after unused bytes
        mstore(0x02, selector)
        mstore(0x06, 0)
        mstore(0x0a, payload)
        result := mload(0x00)
    }
}
```
We can also see this in getSelector, which should instead be shifted left by 48 bits:
```solidity
function getSelector(bytes32 mode) internal pure returns (bytes4) {
    return bytes4(bytes32(uint256(mode) << 16));
}
```
Impact Explanation: The result of this incorrect encoding and decoding is that implementations which make use of this library will not behave correctly when they attempt to use the modeSelector.

## Proof of Concept

no poc

## Recommendation

Fix encoding and decoding logic to correctly place and retrieve the modeSelector. In encodeMode, make the following change:
```solidity
function encodeMode(bytes1 callType, bytes1 execType, bytes4 selector, bytes22 payload)
    internal
    pure
    returns (bytes32 result)
{
    /// @solidity memory-safe-assembly
    assembly {
        mstore(0x00, callType)
        mstore(0x01, execType)
        mstore(0x02, 0)
        mstore(0x06, selector)
        mstore(0x0a, payload)
        result := mload(0x00)
    }
}
```
And in getSelector, make the following change:
```solidity
function getSelector(bytes32 mode) internal pure returns (bytes4) {
    return bytes4(bytes32(uint256(mode) << 48));
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect layout of the 32‑byte mode field defined by the ERC7579 standard. According to the specification, the mode field must be composed of a 1‑byte callType, a 1‑byte execType, four reserved bytes (unused), a 4‑byte modeSelector, and a 22‑byte modePayload, in that exact order. The library implementation (LibERC7579) violates this ordering by writing the modeSelector directly after the execType and before the reserved bytes, and by extracting the selector with a left‑shift of only 16 bits instead of the required 48 bits. This mismatch causes any contract that relies on the library to encode or decode the mode incorrectly: the selector bits are interpreted as part of the reserved region, and the actual selector is shifted out of its intended position. As a result, when a caller supplies a specific execution mode—such as a delegatecall that should not revert on failure—the contract will read a different modeSelector, causing it to perform a staticcall, a batch call, or an unintended error‑handling path. From a user’s perspective the transaction may appear to succeed while the expected behavior (for example, a state‑changing delegatecall or a refund) does not occur, leading to missing balances, zero‑value returns, or funds that seem to disappear. The bug is triggered whenever the encodeMode or getSelector functions are used, which is typical for any ERC7579‑compatible contract that employs LibERC7579 for mode handling. The issue was discovered during a manual security audit that compared the library’s assembly layout against the ERC7579 reference specification; the discrepancy is subtle because the byte‑wise operations succeed without reverting, making the problem hard to detect through ordinary testing. The root cause is a simple ordering mistake in the assembly code and an incorrect bit‑shift constant. To remediate the problem the encoding routine must write four zero bytes after execType before storing the selector, and the selector extraction must shift the 32‑byte word left by 48 bits (instead of 16) before truncating to four bytes. Correcting the layout restores compliance with the ERC7579 mode definition, ensuring that contracts execute with the intended call type and error‑handling semantics, and prevents the silent mis‑execution that can lead to loss of funds or broken business logic.
