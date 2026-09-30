---
id: 22021
severity: "High"
---

# Prover can cheat in `felt_to_bytes_little` due to value underflow

## Description

```solidity
The function `felt_to_bytes_little()` in `bytes.cairo` converts a felt into an array of bytes.

The prover can cheat by returning a near arbitrary string that does not correspond to the input felt, whereby, the spoofed output bytes and `bytes_len, bytes must fulfill some specific conditions (but, if carefully crafted, can contain almost arbitrary sequences of bytes).

This issue affects the function `felt_to_bytes_little()` as well as other functions that depend on it:
    
        - felt_to_bytes()
        - uint256_to_bytes_little()
        - uint256_to_bytes()
        - uint256_to_bytes32()
        - bigint_to_bytes_array()

Those functions are used throughout the code, notably in `get_create_address()` and `get_create2_address()`, which an attacker could exploit to deploy L2 smart contracts from a spoofed sender address (e.g., to steal funds from wallets that use account abstraction).
```

## Proof of Concept

```solidity
To pass the bounds check, we need a code offset that contains the value `0`. Fortunately, from a malicious prover’s perspective, there are many zero-value locations in the code segment. When we dump the memory segment with a hint we find multiple zeroes:
```

## Recommendation

```solidity
The easiest fix is to do range checks on `value` to prevent underflows.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates in the conversion routine that turns a field element (felt) into a little‑endian byte array. The function does not enforce a proper range check on the input value, which allows an underflow condition: a malicious prover can supply a value that is effectively zero at the checked offset while crafting the returned byte array to contain almost any sequence of bytes. Because the conversion routine is used by higher‑level helpers such as get_create_address and get_create2_address, an attacker can manipulate the derived contract address. By presenting a proof that passes the superficial bounds check, the prover can cause the address‑derivation logic to accept a spoofed sender address and consequently deploy a contract that appears to originate from an account the attacker does not control. This can be leveraged to steal funds from wallets that rely on account abstraction, where the expectation is that only the legitimate account owner can trigger contract creation. The issue is discovered during a Code4rena audit through manual inspection of the prover interface and testing of edge‑case inputs that reveal the underflow. It is difficult to notice because the conversion still produces a byte array of the expected length, and the internal consistency checks do not verify that the bytes truly represent the original felt. From a user perspective the symptoms may include a contract appearing under an unexpected address, a balance suddenly becoming zero, or a transaction that should have created a contract from their wallet instead resulting in loss of funds. The impact is high because it breaks the fundamental accounting assumption that address derivation is deterministic and trustworthy. The conceptual fix is to add explicit range validation on the input value before performing the conversion, ensuring that the value fits within the target byte size and preventing the underflow that enables the cheat. By enforcing these checks, the conversion functions and all dependent address‑generation logic become resistant to prover manipulation, restoring confidence that contracts can only be deployed by their legitimate owners.
