---
id: 4883
severity: "High"
---

# Incorrect opcode offset used for Branch Less instruction Submitted by Rhaydden

## Description

The
Rv32BranchLessThan256Chip
uses
the
wrong
opcode
offset
when
creating
its internal BranchLessThanCoreChip.
It uses Rv32LessThan256Opcode::CLASS_OFFSET instead of
Rv32BranchLessThan256Opcode::CLASS_OFFSET. This will cause the branch less than instruction to be
decoded and executed incorrectly.
This affects all 256-bit branch-less-than operations (BLT, BGE, BLTU, BGEU) leading to incorrect branch
condition evaluation.

## Proof of Concept

This part of the code from the Int256::build method shows the issue:
```solidity
extension.rs#L184-L196:
184:
let branch_less_than_chip = Rv32BranchLessThan256Chip::new(
185:
Rv32HeapBranchAdapterChip::new(
186:
execution_bus,
187:
program_bus,
188:
memory_bridge,
189:
address_bits,
190:
bitwise_lu_chip.clone(),
191:
),
192:
BranchLessThanCoreChip::new(
193:
bitwise_lu_chip.clone(),
194:
Rv32LessThan256Opcode::CLASS_OFFSET,
195:
),
196:
offline_memory.clone(),
```
This code will cause branch instructions to be decoded as regular less-than operations which will bypass
control flow checks. Also, this isn't consistent with other patterns seen in other chip implementations
where each chip uses its corresponding opcode's CLASS_OFFSET. For example:
• BaseAluCoreChip uses Rv32BaseAlu256Opcode::CLASS_OFFSET.
• BranchEqualCoreChip uses Rv32BranchEqual256Opcode::CLASS_OFFSET.
If we take a look at core.rs file, we can also see that:
• The BranchLessThanCoreChip is built to handle branch comparison operations with dedicated logic
for:
1. Branch-specific opcode flags:
37:
pub opcode_blt_flag: T,
38:
pub opcode_bltu_flag: T,
39:
pub opcode_bge_flag: T,
40:
pub opcode_bgeu_flag: T,
2. Branch-specific comparison logic that takes care of both signed and unsigned comparisons:
104:
let lt = cols.opcode_blt_flag + cols.opcode_bltu_flag;
105:
let ge = cols.opcode_bge_flag + cols.opcode_bgeu_flag;
106:
let signed = cols.opcode_blt_flag + cols.opcode_bge_flag;
3. Program counter are updated based on comparison results:
159:
let to_pc = from_pc
160:
+ cols.cmp_result * cols.imm
161:
+ not(cols.cmp_result) * AB::Expr::from_canonical_u32(DEFAULT_PC_STEP);
Using Rv32LessThan256Opcode::CLASS_OFFSET instead of Rv32BranchLessThan256Opcode::CLASS_OFFSET
means:
• The opcode validation in core.rs will fail to match the actual instruction opcode.
• The branch-specific flags wont be set correctly.
• The PC updates will be incorrect, potentially causing the program to continue execution at the wrong
address.
• The signed vs unsigned comparison handling will be broken.
The mismatch between the core chip's implementation and the opcode offset used to create it explains
why branch conditions would be evaluated incorrectly.
Also look at this execute_instruction function:
```solidity
217: impl<F: PrimeField32, I: VmAdapterInterface<F>, const NUM_LIMBS: usize, const LIMB_BITS: usize>
218:
VmCoreChip<F, I> for BranchLessThanCoreChip<NUM_LIMBS, LIMB_BITS>
219: where
220:
I::Reads: Into<[[F; NUM_LIMBS]; 2]>,
221:
I::Writes: Default,
222: {
223:
type Record = BranchLessThanCoreRecord<F, NUM_LIMBS, LIMB_BITS>;
224:
type Air = BranchLessThanCoreAir<NUM_LIMBS, LIMB_BITS>;
225:
226:
#[ allow(clippy::type_complexity) ]
227:
fn execute_instruction(
228:
&self,
229:
instruction: &Instruction<F>,
230:
from_pc: u32,
231:
reads: I::Reads,
232:
) -> Result<(AdapterRuntimeContext<F, I>, Self::Record)> {
233:
let Instruction { opcode, c: imm, .. } = *instruction;
234:
let blt_opcode = BranchLessThanOpcode::from_usize(opcode.local_opcode_idx(self.air.offset));
```
The chip converts the opcode using local_opcode_idx(self.air.offset) to get the appropriate branch
operation. Using the wrong offset means branch operations will be incorrectly indexed, executing the
wrong comparison type. The control flow logic in execute_instruction that handles PC updates based
on comparison results will operate on incorrect opcodes.
To demonstrate this, add this import to cargo.toml on line 19:
openvm-bigint-transpiler = { workspace = true }
Add this import to tests.rs on line 15:
use openvm_bigint_transpiler::Rv32LessThan256Opcode;
Then paste this in the same tests.rs file:
**[test]:**
```solidity
#[ should_panic(expected = "attempt to subtract with overflow") ]
fn rv32_branch_lt_wrong_offset_test() {
let bitwise_bus = BitwiseOperationLookupBus::new(BITWISE_OP_LOOKUP_BUS);
let bitwise_chip = SharedBitwiseOperationLookupChip::<RV32_CELL_BITS>::new(bitwise_bus);
let mut tester = VmChipTestBuilder::default();
// Create chip with wrong offset (using LessThan256 instead of BranchLessThan256)
let mut chip_wrong_offset = Rv32BranchLessThanChip::<F>::new(
Rv32BranchAdapterChip::new(
tester.execution_bus(),
tester.program_bus(),
tester.memory_bridge(),
),
BranchLessThanCoreChip::new(bitwise_chip.clone(), Rv32LessThan256Opcode::CLASS_OFFSET),
tester.offline_memory_mutex_arc(),
);
let mut rng = create_seeded_rng();
// Test with values that should trigger a branch
let a = [10, 0, 0, 0];
// Smaller value
let b = [20, 0, 0, 0];
// Larger value
let imm: i32 = 16;
// Branch offset
let rs1 = gen_pointer(&mut rng, 4);
let rs2 = gen_pointer(&mut rng, 4);
tester.write::<RV32_REGISTER_NUM_LIMBS>(1, rs1, a.map(F::from_canonical_u32));
tester.write::<RV32_REGISTER_NUM_LIMBS>(1, rs2, b.map(F::from_canonical_u32));
// This should fail due to incorrect opcode offset causing overflow
let from_pc = rng.gen_range(imm.unsigned_abs()..(1 << (PC_BITS - 1)));
tester.execute_with_pc(
&mut chip_wrong_offset,
&Instruction::from_isize(
BranchLessThanOpcode::BLT.global_opcode(),
rs1 as isize,
rs2 as isize,
imm as isize,
1,
1,
),
from_pc,
);
// We shouldn't reach this point
panic!("Test should have failed with overflow error");
}
```
Logs:
Blocking waiting for file lock on build directory
Compiling openvm-rv32im-circuit v1.0.0-rc.1 (/Users/rhaydden/openvm/extensions/rv32im/circuit)
Finished `test` profile [optimized + debuginfo] target(s) in 15.75s
Running unittests src/lib.rs (target/debug/deps/openvm_rv32im_circuit-9408da59e6f0f62e)
running 1 test
thread 'branch_lt::tests::rv32_branch_lt_wrong_offset_test' panicked at
crates/toolchain/instructions/src/lib.rs:38:9:
attempt to subtract with overflow
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
test branch_lt::tests::rv32_branch_lt_wrong_offset_test - should panic ... ok
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 173 filtered out; finished in 0.07s
Test logs actually show that when BranchLessThanOpcode::BLT.global_opcode() is used in the instruc-
tion:
• This gives us a global opcode for the BLT operation.
• The chip tries to map this global opcode to a local opcode using opcode.local_opcode_idx(self.air.offset).
• But we provided Rv32LessThan256Opcode::CLASS_OFFSET instead of Rv32BranchLessThan256Opcode::CLASS_OFFSET.
The overflow happens because:
• The global opcode for BLT is in the branch instruction range.
• When we subtract the wrong offset (Rv32LessThan256Opcode::CLASS_OFFSET), which is in a different
range.
• We get an invalid result that causes arithmetic overflow.

## Recommendation

The
BranchLessThanCoreChip
within
the
Rv32BranchLessThan256Chip
should make use of the opcode offset specifically for the branch less than instruction, which is
Rv32BranchLessThan256Opcode::CLASS_OFFSET. Using the less than opcode offset will result in incorrect
behavior.
```solidity
BranchLessThanCoreChip::new(
bitwise_lu_chip.clone(),
-
Rv32LessThan256Opcode::CLASS_OFFSET,
+
Rv32BranchLessThan256Opcode::CLASS_OFFSET,
),
offline_memory.clone(),
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect opcode offset used when constructing the internal BranchLessThanCoreChip of the Rv32BranchLessThan256Chip. Instead of using the dedicated branch‑less‑than class offset (Rv32BranchLessThan256Opcode::CLASS_OFFSET), the implementation mistakenly supplies the generic less‑than class offset (Rv32LessThan256Opcode::CLASS_OFFSET). This mismatch causes the virtual machine to decode branch‑less‑than instructions (BLT, BGE, BLTU, BGEU) as regular less‑than operations. As a result the branch‑specific flags are never set, the comparison result is computed incorrectly, and the program counter update logic uses a wrong opcode index. When a conditional branch should be taken, the VM either skips the branch, jumps to an unintended address, or triggers an arithmetic overflow during the local opcode calculation. The impact is that control‑flow checks can be bypassed, leading to unexpected execution paths, potential loss of funds, or protocol state corruption. The bug manifests whenever the chip is instantiated with the wrong offset, which occurs in the Int256::build method and therefore affects all 256‑bit branch‑less‑than operations. Users experience symptoms such as a conditional transfer not occurring, balances remaining unchanged, or a transaction reverting with an overflow error, contrary to the expectation that the branch condition would be evaluated correctly. The issue was discovered during a security audit by reviewing the chip construction patterns and confirming the inconsistency with other chips, and it was reproduced with a test that panics due to overflow. It is hard to notice because the contract compiles and runs, but the branch logic fails only under specific conditions, making the failure subtle. The proper fix is to replace the incorrect offset with Rv32BranchLessThan256Opcode::CLASS_OFFSET when creating the BranchLessThanCoreChip, ensuring that branch‑specific opcode validation, flag setting, and PC update logic operate on the correct instruction class. This bug belongs to the class of opcode‑misalignment or control‑flow decoding errors, where an instruction is interpreted with the wrong opcode class, breaking the accounting assumptions of conditional execution.
