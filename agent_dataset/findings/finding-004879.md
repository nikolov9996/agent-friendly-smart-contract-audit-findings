---
id: 4879
severity: "High"
---

# Invalid Divrem chip row can send arbitrary bitwise range check with multiplicity -1 (equivalent to receive) Submitted by cergyk

## Description

Divrem chip uses bitwise range check (check that two F numbers are valid 16 bits limbs), with
multiplicity is_valid - special_case. Unfortunately it is not constrained that special_case can only be
true when is_valid is true, which means that the prover can insert a row which will emit the send_range
over the bitwise bus with multiplicity -1 (equivalent to "receiving" the range check).
```solidity
self.bitwise_lookup_bus
.send_range(cols.lt_diff - AB::Expr::ONE, AB::F::ZERO)
.eval(builder, is_valid.clone() - special_case);
```
This means that the prover can prove that any pair (F, 0) is a valid pair of 16 bit limbs, and forge results
of any other chips using out of range limb values normally checked by send_range over the bitwise bus.
Note that there is the constraint that second pair argument for the receive is necessary a zero.
Additionally note that a similar expression is used in modular_chip, where is_setup is correctly con-
strained to be only 1 when is_valid:
```solidity
modular_chip/is_eq.rs#L122:
builder.when(cols.is_setup).assert_one(cols.is_valid);
modular_chip/is_eq.rs#L209-L214:
self.bus
.send_range(
cols.b_lt_diff - AB::Expr::ONE,
cols.c_lt_diff - AB::Expr::ONE,
)
.eval(builder, cols.is_valid - cols.is_setup);
```

## Proof of Concept

no poc

## Recommendation

Apply the same type of constraint on the divrem chip (divrem/core.rs#L280-L282):
```solidity
+ self.builder.when(special_case).assert_one(is_valid.clone());
self.bitwise_lookup_bus
.send_range(cols.lt_diff - AB::Expr::ONE, AB::F::ZERO)
.eval(builder, is_valid.clone() - special_case);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the division‑remainder (divrem) chip of the zkVM circuit. The chip performs a bitwise range check to ensure that two field elements represent valid 16‑bit limbs. This check is emitted on a dedicated bitwise lookup bus with a multiplicity that is calculated as is_valid minus special_case. Because the circuit does not enforce that the special_case flag can be true only when is_valid is also true, a prover can construct a row where special_case is true while is_valid is false. In that situation the multiplicity becomes -1, which is equivalent to receiving the range‑check on the bus rather than sending it. The negative multiplicity effectively cancels the original range‑check, allowing the prover to claim that any pair (F,0) satisfies the 16‑bit limb constraint. Consequently the prover can forge the results of downstream chips that rely on the bitwise range check, inserting out‑of‑range limb values that would normally be rejected. The bug is triggered whenever a proof includes a divrem chip row with the unconstrained special_case flag; it does not depend on external inputs but on the prover’s ability to manipulate the circuit’s internal flags. The impact is that a malicious prover can produce a proof that appears mathematically valid while containing incorrect arithmetic, such as division or remainder results that do not match the true values. This can lead to protocol‑level mis‑accounting, allowing funds to be transferred incorrectly, balances to disappear, or state transitions to be accepted based on false calculations. Users, auditors, and any protocol that relies on the divrem chip for correct arithmetic are affected because the integrity of the proof is compromised. The issue was discovered during a manual audit of the circuit code, where the auditor noticed that the modular chip correctly asserts that is_setup implies is_valid, but the divrem chip lacks an analogous constraint. The bug is subtle because the range‑check still appears in the circuit trace, but the negative multiplicity masks its effect, making it hard to detect with standard functional tests that only exercise valid inputs. To remediate the problem, a constraint must be added that forces is_valid to be one whenever special_case is asserted, mirroring the pattern used in the modular chip. This ensures that the multiplicity can never become negative, preserving the intended bitwise range validation and preventing the prover from cancelling the check. In abstract terms, the flaw belongs to the class of unchecked flag interactions that enable multiplicity manipulation, leading to range‑check bypasses and arithmetic forgery in zero‑knowledge circuits.
