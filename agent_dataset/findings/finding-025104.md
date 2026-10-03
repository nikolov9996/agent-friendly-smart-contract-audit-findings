---
id: 25104
severity: "Medium"
---

# Codeup::claimCodeupERC20() may revert whenever the weth balance is very low

## Description

`Codeup::claimCodeupERC20()` adds liquidity to the `Uniswap` pool whenever the `weth` balance is bigger than `1`. However, an amount bigger than `1` may still lead to reverts if it is low enough. If it is exactly 1, it will shift right to get the amount of `weth` to swap for `CodeupERC20`, trying to swap an amount of `0` and reverting. If it is bigger than 2, but still low, it may swap this for an even smaller amount of `CodeupERC20`, reverting when adding liquidity due to not providing enough liquidity to mint a single share. A [poc](<https://github.com/0x73696d616f/codeup-issues-external/blob/main/test/Codeup.t.sol#L146>) is available to confirm the finding.

## Proof of Concept

No PoC provided.

## Recommendation

Instead of setting `1`, a slightly bigger dust amount could be use to ensure it does not revert.
