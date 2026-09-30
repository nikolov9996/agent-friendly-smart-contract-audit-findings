---
id: 22023
severity: "High"
---

# Non-finalized dictionary in RIPEMD160 allows forging of output

## Description

```solidity
When [`ripemd160.finish()`](https://github.com/kkrt-labs/kakarot/blob/7411a5520e8a00be6f5243a50c160e66ad285563/src/kakarot/precompiles/ripemd160.cairo#L427) does not enter the `if (next_block == FALSE)` condition at L456, the dictionary `x` initialized at the beginning of the function is not finalized. Instead, `x` is reassigned to reference a new dictionary at L470:
    
    File: ripemd160.cairo
    456:     if (next_block == FALSE) {
    			 ...
    462:         default_dict_finalize(start, x, 0);
    463:         let (res, rsize) = compress(buf, bufsize, arr_x, 16);
    464:         return (res=res, rsize=rsize);
    465:     }
    466:     let (local arr_x: felt*) = alloc();
    467:     dict_to_array{dict_ptr=x}(arr_x, 16);
    468:     let (buf, bufsize) = compress(buf, bufsize, arr_x, 16);
    469:     // reset dict to all 0.
    470:     let (x) = default_dict_new(0);

Because the old dictionary is never finalized, it is possible to insert incorrect values for read operations on the old dictionary, which allows proving an incorrect output for any input of `size > 55` (56 with the fix to our separate vulnerability on this value).

Read operations on the old dictionary are performed in [`ripemd160::absorb_data`](https://github.com/kkrt-labs/kakarot/blob/7411a5520e8a00be6f5243a50c160e66ad285563/src/kakarot/precompiles/ripemd160.cairo#L148):
    
    File: ripemd160.cairo
    148: func absorb_data{range_check_ptr, bitwise_ptr: BitwiseBuiltin*, dict_ptr: DictAccess*}(
    149:     data: felt*, len: felt, index: felt
    150: ) {
    151:     alloc_locals;
    152:     if (index - len == 0) {
    153:         return ();
    154:     }
    155: 
    156:     let (index_4, _) = unsigned_div_rem(index, 4);
    157:     let (index_and_3) = uint32_and(index, 3);
    158:     let (factor) = uint32_mul(8, index_and_3);
    159:     let (factor) = pow2(factor);
    160:     let (tmp) = uint32_mul([data], factor);
    161:     let (old_val) = dict_read{dict_ptr=dict_ptr}(index_4);
    162:     let (val) = uint32_xor(old_val, tmp);
    163:     dict_write{dict_ptr=dict_ptr}(index_4, val);
    164: 
    165:     absorb_data{dict_ptr=dict_ptr}(data + 1, len, index + 1);
    166:     return ();
    167: }
```

## Proof of Concept

```solidity
The below test case can be added to `test_ripemd160.py` to demonstrate the vulnerability:
    
    async def test_ripemd160_output_can_be_forged(self, cairo_program, cairo_run):
    	msg_bytes = bytes([0x00] * 57)
    	with (
    		patch_hint(
    			cairo_program,
    			"vm_enter_scope()",
    			"try:\n"
    			"    dict_tracker = __dict_manager.get_tracker(ids.dict_ptr)\n"
    			"    dict_tracker.data[ids.index_4] = 1\n"
    			"except Exception: pass\n"
    			"vm_enter_scope()"
    		)
    	):
    		precompile_hash = cairo_run("test__ripemd160", msg=list(msg_bytes))
```

## Recommendation

```solidity
Call `default_dict_finalize(start, x, 0);` before `let (x) = default_dict_new(0);`.
```

Severity: High

[PR](https://github.com/kkrt-labs/kakarot/pull/1577) fix: finalize dictionary in `RIPEMD160`. Finalizes the `dict` and reassign to start after resetting the `dict`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the RIPEMD160 precompile implementation where the internal dictionary used to accumulate intermediate state is not properly finalized before being replaced. In the finish routine, when processing a message that spans more than one 55‑byte block, the code follows a path where the condition checking for the final block is false, causing the function to allocate a new dictionary with default_dict_new without first calling default_dict_finalize on the existing dictionary. Because the old dictionary remains unfinalized, its entries stay mutable and can be overwritten by subsequent absorb_data calls that perform dict_write operations. An attacker can exploit this by injecting a crafted value into the dictionary after the first block, for example by patching the execution hint to modify dict_tracker.data at the computed index. This manipulation changes the XOR‑based accumulation used in the hash compression, allowing the attacker to produce an arbitrary hash output for any input longer than 55 bytes. The impact is that the RIPEMD160 hash, which many contracts rely on for integrity checks, signatures, or Merkle proofs, can be forged, potentially breaking protocol guarantees and enabling malicious actors to bypass verification steps. The bug manifests only when the input size exceeds the single‑block threshold and when the next_block flag is true, meaning it is invisible for short messages and therefore easy to miss during casual testing. Users experience a mismatch between the expected hash (e.g., they expect a correct RIPEMD160 digest) and the actual value returned, often seeing a completely unrelated hash or a hash that matches an attacker‑chosen pattern, leading to failed transactions or rejected proofs. The issue was discovered during a Code4rena audit by adding a test that patches the dictionary tracker and observes that the output can be forged. It is hard to notice because the function appears to work correctly for short inputs and the internal dictionary handling is not exposed at the interface level. The bug belongs to the class of improper resource finalization or state leakage, similar to use‑after‑free vulnerabilities, where stale mutable state persists across logical phases. The correct mitigation is to ensure that default_dict_finalize is invoked on the current dictionary before allocating a new one, thereby sealing the old state and preventing any further writes. This conceptual fix restores the intended immutability of the hash computation and eliminates the ability to forge outputs.
