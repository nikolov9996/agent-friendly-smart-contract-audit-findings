---
id: 18314
severity: "High"
---

# `LotteryMath.calculateNewProfit` returns wrong profit when there is no jackpot winner

## Description

```solidity
currentNetProfit = LotteryMath.calculateNewProfit(
    currentNetProfit,
    ticketsSold[drawFinalized],
    ticketPrice,
    jackpotWinners > 0,
    fixedReward(selectionSize),
    expectedPayout
);
```
`Lottery.currentNetProfit` is used during reward calculation, so it can ruin the main functionality of this protocol.
```solidity
function drawRewardSize(uint128 drawId, uint8 winTier) private view returns (uint256 rewardSize) {
    return LotteryMath.calculateReward(
        currentNetProfit,
        fixedReward(winTier), 
        fixedReward(selectionSize),
        ticketsSold[drawId],
        winTier == selectionSize,
        expectedPayout
    );
}
```

## Proof of Concept

In `LotteryMath.calculateNewProfit`, `expectedRewardsOut` is calculated as follows:
```solidity
uint256 expectedRewardsOut = jackpotWon
    ? calculateReward(oldProfit, fixedJackpotSize, fixedJackpotSize, ticketsSold, true, expectedPayout)
    : calculateMultiplier(calculateExcessPot(oldProfit, fixedJackpotSize), ticketsSold, expectedPayout)
        * ticketsSold * expectedPayout;
```
The calculation is not correct when there is no jackpot winner. When `jackpotWon` is false, `ticketsSold * expectedPayout` is the total payout in reward token, and then we need to apply a multiplier to the total payout, and the multiplier is `calculateMultiplier(calculateExcessPot(oldProfit, fixedJackpotSize), ticketsSold, expectedPayout)`.

The calculation result is `expectedRewardsOut`, and it is also in reward token, so we should use `PercentageMath` instead of multiplying directly.

For coded PoC, I added this function in `LotteryMath.sol` and imported `forge-std/console.sol` for console log.
```solidity
function testCalculateNewProfit() public {
    int256 oldProfit = 0;
    uint256 ticketsSold = 1;
    uint256 ticketPrice = 5 ether;
    uint256 fixedJackpotSize = 1_000_000e18; // don't affect the profit when oldProfit is 0, use arbitrary value
    uint256 expectedPayout = 38e16;
    int256 newProfit = LotteryMath.calculateNewProfit(oldProfit, ticketsSold, ticketPrice, false, fixedJackpotSize, expectedPayout );

    uint256 TICKET_PRICE_TO_POT = 70_000;
    uint256 ticketsSalesToPot = PercentageMath.getPercentage(ticketsSold * ticketPrice, TICKET_PRICE_TO_POT);
    int256 expectedProfit = oldProfit + int256(ticketsSalesToPot);
    uint256 expectedRewardsOut = ticketsSold * expectedPayout; // full percent because oldProfit is 0
    expectedProfit -= int256(expectedRewardsOut);
    
    console.log("Calculated value (Decimal 15):");
    console.logInt(newProfit / 1e15); // use decimal 15 for output purpose

    console.log("Expected value (Decimal 15):");
    console.logInt(expectedProfit / 1e15);
}
```
The result is as follows:
```
  Calculated value (Decimal 15):
  -37996500
  Expected value (Decimal 15):
  3120
```

## Recommendation

```solidity
uint256 expectedRewardsOut = jackpotWon
    ? calculateReward(oldProfit, fixedJackpotSize, fixedJackpotSize, ticketsSold, true, expectedPayout)
    : (ticketsSold * expectedPayout).getPercentage(
        calculateMultiplier(calculateExcessPot(oldProfit, fixedJackpotSize), ticketsSold, expectedPayout)
    );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the profit‑updating routine of the lottery contract, specifically the function that computes the new net profit after a draw. When a draw finishes without a jackpot winner, the routine calculates the expected reward payout by multiplying the total ticket payout (ticketsSold × expectedPayout) with a multiplier derived from the excess pot. Instead of applying the multiplier as a percentage, the code multiplies the raw values directly, bypassing the PercentageMath utility that would correctly scale the amount. This arithmetic mistake causes the expectedRewardsOut value to be dramatically inflated or deflated, which in turn corrupts the currentNetProfit variable that is later used to determine individual rewards. The root cause is a logical error in the reward formula: the multiplier is treated as a raw factor rather than a percentage, leading to an incorrect profit delta. An attacker or any user can trigger a draw where no jackpot is won – a normal scenario in a lottery – and the contract will record a net profit that is far lower (or even negative) than it should be. As a result, subsequent reward calculations may under‑pay winners, produce zero payouts, or, conversely, allow the contract to over‑draw from the pot, effectively making funds disappear from the protocol’s accounting. From a user’s point of view the symptom is that a participant who expects a refund or a prize receives nothing or a much smaller amount than advertised, and the protocol’s balance may show unexpected deficits. The issue was uncovered during a formal audit by reproducing the calculation with a test harness that logged the intermediate values; the logged profit differed by several orders of magnitude from the mathematically expected result, confirming the mis‑calculation. Because the faulty variable is internal and only manifests as an accounting discrepancy, it can be hard to notice without explicit testing of the no‑jackpot path. The proper fix is to replace the direct multiplication with a percentage‑based computation, for example by using PercentageMath.getPercentage on the product of ticketsSold, expectedPayout and the multiplier, as illustrated in the recommended code snippet. Conceptually, the bug belongs to the class of “incorrect financial scaling” or “percentage‑math misuse” bugs, where a factor intended to represent a percent is applied as a raw multiplier, breaking the economic invariants of the contract.
