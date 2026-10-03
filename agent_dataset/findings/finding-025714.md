---
id: 25714
severity: "Crit/High"
---

# Distribute is permissionless, allowing malicious users to specify 0 slippage and sandwich the swap

## Description

distribute() uses the argument [amountOutMinimum](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L300>) as slippage control, but the function is permissionless, so malicious users can trigger swaps with 0 minimum amount out.

## Proof of Concept

No PoC provided.

## Recommendation

Set up a keeper role to distribute rewards.
