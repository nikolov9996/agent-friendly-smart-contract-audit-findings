---
id: 25279
severity: "Crit/High"
---

# Lack of deadline in PowerToken.buy can lead to user's cashToken being distributed through ZeroToken holders

## Description

The function [PowerToken.buy](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/PowerToken.sol#L102-L122>) is used to purchase tokens in auction. The price of those tokens decreases with time, following a dutch auction model.

Because there's no deadline parameter in the function call, it's possible to retain this transaction and execute it in a subsequent auction at a steeper price, potentially resulting in a significant loss to the user, considering the price in an auction starts at 2^99 wei per supply basis point. Here's a likely scenario:

1. Auction A starts. Let's assume that cashToken is WETH.
2. Nobody buys the tokens until the price becomes more reasonable. For example, 1 ether per bps.
3. Alice max-approves the spending of her WETH for the PowerToken contract to transfer them. Alice holds 100 WETH in her wallet.
4. Alice tries to buy the tokens, but ends up paying a very low fee and the transaction ends up not being picked up for execution. In the meantime, market fees rise and the transaction gets stuck in the mempool. This is not uncommon, and there are thousands of mempool transactions with over a month.
5. A new auction B eventually starts. Starting price is the same.

6. A ZeroToken holder Bob submits Alice's transaction inside a flashbots bundle. Bob does this when the price is 100 ether per bps.
7. Alice ends up buying the desired amount of PowerToken. However, the price was much larger than she wanted, and she ended up spending 100 times more.
8. The WETH falls into the vault, where both Bob and the other ZeroToken holders will be able to claim their fair share. It should be noted that, in theory, all ZeroToken holders have an economic incentive to be on the look for these buying attempts that get stuck on the mempool.

## Proof of Concept

No PoC provided.

## Recommendation

Add a deadline input to the function call, and check that block.timestamp is smaller than that deadline.

```solidity
function buy( uint256 minAmount_, uint256 maxAmount_, address destination_, uint256 deadline_ ) external returns (uint240 amount_, uint256 cost_) {
```
