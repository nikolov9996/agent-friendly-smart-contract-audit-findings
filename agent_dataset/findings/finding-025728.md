---
id: 25728
severity: "Low/Info"
---

# IERC20Base Noncompliant With ERC20 Standard

## Description

The interface declares [increaseAllowance and decreaseAllowance](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/50601071fb44010524ce4d667c5c881af1b2533e/contracts/interfaces/IERC20Base.sol#L31-L37>) functions, which aren't part of the official [ERC20](<https://eips.ethereum.org/EIPS/eip-20>) standard.

Calls to such functions may revert with some tokens. However, these functions are part of the [OpenZeppelin's ERC20 implementation](<https://docs.openzeppelin.com/contracts/2.x/api/token/erc20#ERC20>) designed to mitigate well-known issues around setting allowances. It's important to note that these functions do not entirely fix these issues.

An [example](<https://github.com/d-xo/weird-erc20?tab=readme-ov-file#approval-race-protections>) is USDT and its "approval race protection," which causes other issues.

Additionally, the decimals() function is optional, and contracts mustn't rely on it.

## Proof of Concept

No PoC provided.

## Recommendation

It's advisable to use [OpenZeppelin's SafeERC20 lib](<https://docs.openzeppelin.com/contracts/2.x/api/token/erc20#SafeERC20>), not only for dealing with allowances but also with transfers, without reinventing the wheel, as seen in ERC20Helper.sol.
