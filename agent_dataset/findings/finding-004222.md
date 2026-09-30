---
id: 4222
severity: "High"
---

# Using timeToTransmute instead of transmutationTime affects already created redemptions

## Description

```solidity
uint256 blocksLeft = position.maturationBlock > block.number ? position.maturationBlock - block.number : 0;
uint256 amountNottransmuted = blocksLeft > 0 ? position.amount * blocksLeft / timeToTransmute : 0;
uint256 amountTransmuted = position.amount - amountNottransmuted;
```
The global variable timeToTransmute determines the duration that new redemptions must wait before completely transmuting. According to the team, the Transmuter is designed so that the total time required for maturity is established when a redemption is created.
By using the variable timeToTransmute here, the maturation time for an existing position is affected when the global variable is updated, which is not intended.
Furthermore, as the correct maturation times are used for updating and querying the staking graph, the earmarking accounting would become incorrect, and either too little or too much would be earmarked as timeToTransmute changed.

## Proof of Concept

timeToTransmute is set to 200,000 blocks, roughly 28 days.
• User A creates a redemption for 10,000 alUSD at block T. The maturation block is set to T + 200,000.
• A week and 50,000 blocks later, due to increasing yield and an unstable alUSD peg, timeToTransmute is halved to 100,000 blocks.
• User A decides to exit because they need liquidity. Their position has matured for a week, so their remaining position should be 7,500 alUSD, and they should receive the rest (valued at 2,500 USD) in yield tokens.
• Due to the above calculation, however, their remaining position will be calculated to:
```solidity
uint256 blocksLeft = T + 200_000 > T + 50_000 ? T + 200_000 - (T + 50_000) : 0;
// 150_000
uint256 amountNottransmuted = 150_000 > 0 ? 10_000 * 150_000 / 100_000 : 0;
// 15_000
uint256 amountTransmuted = 10_000 - 15_000;
// Underflow!
```
• Because timeToTransmute halved, User A's remaining debt immediately doubled to 15,000, which is higher than their original deposit. As a result of transmutation times in general decreasing, theirs, and all existing positions, had their maturation time increased. User A would now have to wait another week until they even start transmuting.
• Another week and 50,000 blocks go by. It's been a total of 100,000 blocks since Users A and B created their positions. At this time, timeToTransmute is increased to 400,000 blocks.
• At this point, User A decides to try to exit again. Their position should be half matured, and they should have approximately 5,000 debt tokens left to transmute and receive yield tokens worth 5,000 USD, minus fees.
• However, they get the following calculation:
```solidity
uint256 blocksLeft = T + 200_000 > T + 100_000 ? T + 200_000 - (T + 100_000) : 0;
// 100_000
uint256 amountNottransmuted = 100_000 > 0 ? 10_000 * 100_000 / 400_000 : 0;
// 2_500
uint256 amountTransmuted = 10_000 - 2_500;
//
```
• User A thus is considered 3/4ths matured. As a result of maturation times generally increasing, theirs went down significantly.

## Recommendation

Further down in the code, there is the following line:
```solidity
uint256 transmutationTime = position.maturationBlock - position.startBlock;
```
Move that line up to before the problematic line and replace timeToTransmute in the denominator with transmutationTime.

## Derived Narrative

The following field is derived content and may not be source-grounded:

Using a global timeToTransmute constant in the redemption maturity calculation creates a time‑dependent accounting bug. The contract stores a position with a startBlock and a maturationBlock that is set when the redemption is created. The amount that has not yet transmuted is calculated as position.amount * blocksLeft / timeToTransmute, where blocksLeft is the difference between the stored maturationBlock and the current block number. Because timeToTransmute is a mutable global variable, any later change to this parameter retroactively changes the denominator for all existing positions. When the global value is decreased, the denominator becomes smaller, causing the computed amountNottransmuted to increase, potentially exceeding the original position.amount and triggering an under‑flow when amountTransmuted is derived as position.amount - amountNottransmuted. Conversely, when the global value is increased, the denominator grows and the contract reports a larger portion of the position as already transmuted, shortening the perceived remaining maturity. This mismatch breaks the accounting invariants of the staking graph, leads to incorrect earmarking of yield, and can make users unable to exit their positions or receive an unexpected amount of debt or yield tokens. The bug manifests only after the protocol adjusts timeToTransmute, for example in response to market conditions, and is hard to notice because the calculation itself appears syntactically correct and the contract continues to emit the expected events. The issue was discovered during a manual audit that examined how maturation times are stored and how they are used in later accounting functions. From a user’s point of view the UI may show that a redemption is partially matured, but when the user attempts to claim they either receive zero tokens, an amount larger than their original deposit, or the transaction reverts due to an arithmetic under‑flow. The vulnerability belongs to the class of mutable‑parameter accounting bugs where a global configuration variable is used in per‑instance calculations that are assumed to be immutable. The correct fix is to compute a per‑position transmutationTime as maturationBlock - startBlock at the moment the redemption is created and to use that constant value in the denominator of the amountNottransmuted formula, thereby decoupling existing positions from future changes to the global timeToTransmute.
