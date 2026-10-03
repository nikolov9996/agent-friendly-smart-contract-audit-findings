---
id: 25393
severity: "Low/Info"
---

# Codebase is not using SafeERC20

## Description

The codebase is using transferFrom() and transfer() which revert for weird ERC20 tokens. It should not happen as the MetaZero token implements the standard [correctly](<https://etherscan.io/address/0x328a268b191ef593b72498a9e8a481c086eb21be#code>).

## Proof of Concept

No PoC provided.

## Recommendation

Use [SafeERC20::safeTransferFrom()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/utils/SafeERC20.sol#L44>) and [SafeERC20::safeTransfer()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/utils/SafeERC20.sol#L36>) instead.
