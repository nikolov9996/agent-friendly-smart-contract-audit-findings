---
id: 25602
severity: "Low/Info"
---

# ERC20AssetPool and ERC721AssetPool should have the nonReentrant modifier as ERC721 and some tokens have callbacks

## Description

ERC721 implements a callback when transferring tokens. Some tokens, such as ERC777 implement callbacks when transferring. Both these tokens could lead to reentrancy.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the nonReentrant modifier for ERC20AssetPool and ERC721AssetPool.
