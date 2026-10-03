---
id: 25077
severity: "Medium"
---

# Fee on transfer tokens transfer less tokens than what is stored in the receipt on deposits

## Description

Some tokens have a fee on transfer, such as USDT, although it is disabled currently [(line 127](<https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7#code>) and 177).

This means that on deposits, the actually deposited amount to the smart contract will not be the one passed as argument, but its value minus the fee.

Thus, for example, the [`Batch.sol`](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L247>) contract will hold less funds than stored, potentially leading to withdrawal failure.

## Proof of Concept

No PoC provided.

## Recommendation

The actual transferred amount is the balance after minus the balance before the transfer. Modify [this](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouter.sol#L491>) line to:

```solidity
uint256 previousBalance = IERC20(depositToken).balanceOf(address(batch));
IERC20(depositToken).safeTransferFrom(msg.sender, address(batch), depositAmount);
depositAmount = IERC20(depositToken).balanceOf(address(batch)) previousBalance;
```

Also, place the lines above before calling batch.deposit().
