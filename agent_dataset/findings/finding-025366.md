---
id: 25366
severity: "Low/Info"
---

# Extra spaces found in some instances of the codebase

## Description

Some extra spaces were found in the codebase which could be fixed for increased readability.

## Proof of Concept

No PoC provided.

## Recommendation

- `bytes32 public immutable  override poolId;` in SyrupUserActions.
- `// 4. If asset out is USDC, swap DAI  to USDC` in SyrupUserActions::_swap().
