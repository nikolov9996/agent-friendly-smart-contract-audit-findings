---
id: 19206
severity: "High"
---

# User doesn’t have to deposit for a week into the market to get their weekly reward from the `LendingLedger`

## Description

In the `LendingLedger` contract, a user is rewarded with CANTO tokens depending on how long he has his deposit in the market. Rewards are distributed for each week during which the deposit was inside the market. However, the user can cheat this condition because we are rounding down to the start of the week, so the user can deposit at 23:59 at the end of the week and withdraw at 00:00 and still get rewarded as if he had his deposit for the whole week.

## Proof of Concept

Test case for the `LendingLedger.t.sol`

```solidity
function setupStateBeforeClaim() internal {
    whiteListMarket();

    vm.prank(goverance);
    ledger.setRewards(0, WEEK*10, amountPerEpoch);

    // deposit into market at 23:59 (week 4)
    vm.warp((WEEK * 5) - 1);

    int256 delta = 1.1 ether;
    vm.prank(lendingMarket);
    ledger.sync_ledger(lender, delta);

    // airdrop ledger enough token balance for user to claim
    payable(ledger).transfer(1000 ether);
    // withdraw at 00:00 (week 5)
    vm.warp(block.timestamp + 1);
    vm.prank(lendingMarket);
    ledger.sync_ledger(lender, delta * (-1));
}

function testClaimValidLenderOneEpoch() public {
    setupStateBeforeClaim();

    uint256 balanceBefore = address(lender).balance;
    vm.prank(lender);
    ledger.claim(lendingMarket, 0, type(uint256).max);
    uint256 balanceAfter = address(lender).balance;
    assertTrue(balanceAfter - balanceBefore == 1 ether);

    uint256 claimedEpoch = ledger.userClaimedEpoch(lendingMarket, lender);
    assertTrue(claimedEpoch - WEEK*4 == WEEK);
}
```

## Recommendation

It’s difficult to propose a solution for this exploit without major changes in the contract’s architecture. Perhaps we can somehow split the amount based on the time the sync was made inside the week, let’s say Alice’s `last_sync` was in the middle of week0, she deposited 1 ether, thus her amount for the current epoch will be 1/2 ether. However there is a caveat, how do we fill the gaps? We can’t fill them with 1/2 ether. We can use this struct though,

```solidity
Amount {
    uint256 actualAmount,
    uint256 fraction
}
```

so we can use `fraction` for the current epoch and `actualAmount = 1 ether` to fill the gaps.

Chosen as best due to clarity, conciseness, and presence of executable PoC

The rationale behind the High severity is that the purpose of veRWA is to attract liquidity to certain contracts as voted by CANTO holders, and this vulnerability defeats the purpose of attracting liquidity completely.

Reward calculation is now based on a time-weighted balance. Btw, while implementing the fix I noticed that the PoC here does not really highlight the problem. In the PoC, there is only one lender, so even if we take the deposit time into account, this lender should receive 100% of the epoch rewards (as they provided 100% of the liquidity within the market during this epoch). I modified the PoC to a scenario where there are two lenders, with one that deposited only for one second and one for the whole week. The one that deposited for the whole week should receive ~604800 times more rewards for this epoch, which is now the case:

```solidity
function testTimeWeightedClaiming() public {
    whiteListMarket();
    int256 delta = 1.1 ether;

    vm.prank(goverance);
    ledger.setRewards(0, WEEK*10, amountPerEpoch);
    vm.startPrank(lendingMarket);
    // users[2] deposits at beginning of epoch
    vm.warp(WEEK * 4);
    ledger.sync_ledger(users[2], delta);
    // lender deposits at 23:59 (week 4)
    vm.warp((WEEK * 5) - 1);

    ledger.sync_ledger(lender, delta);
    vm.stopPrank();

    // airdrop ledger enough token balance for user to claim
    payable(ledger).transfer(1000 ether);
    // withdraw at 00:00 (week 5)
    vm.warp(WEEK * 5);
    vm.prank(lendingMarket);
    ledger.sync_ledger(lender, delta * (-1));

    uint256 balanceBefore = address(lender).balance;
    vm.prank(lender);
    ledger.claim(lendingMarket, 0, type(uint256).max);
    uint256 balanceAfter = address(lender).balance;
    // Lender should receive rewards for 1 second
    assertEq(balanceAfter - balanceBefore, 1 * 1 ether * 1.1 ether / (1.1 ether * WEEK + 1.1 ether));
    uint256 balanceBefore2 = address(users[2]).balance;
    vm.prank(users[2]);
    ledger.claim(lendingMarket, 0, type(uint256).max);
    uint256 balanceAfter2 = address(users[2]).balance;
    // User2 should receive rewards for 1 week
    assertEq(balanceAfter2 - balanceBefore2, WEEK * 1 ether * 1.1 ether / (1.1 ether * WEEK + 1.1 ether));
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the LendingLedger contract determines a lender’s weekly CANTO reward. Rewards are allocated per epoch that is defined as a whole week, and the contract computes the eligible time by truncating the deposit timestamp to the start of the week. Because of this rounding, a user can deposit a fraction of a second before the week ends (for example at 23:59:59) and withdraw immediately after the new week begins (00:00:00). The contract still treats the deposit as having been present for the entire week and therefore credits the full weekly reward even though the actual holding time was only a second. The root cause is the use of a coarse, week‑aligned time bucket without accounting for the precise duration a deposit was active within that bucket. An attacker can exploit this by repeatedly performing end‑of‑week deposits and withdrawals, harvesting rewards that are disproportionate to the liquidity actually provided. The impact is a systematic over‑allocation of reward tokens, which reduces the pool available for honest liquidity providers and defeats the economic incentive model of veRWA that relies on time‑weighted balances. The condition occurs whenever the reward period is measured in whole weeks and the contract rounds timestamps down to the week start; it affects any lender interacting with the market, the protocol’s token economics, and ultimately CANTO holders who expect rewards to reflect genuine liquidity provision. The issue was discovered during a security audit when a test case demonstrated that a lender could claim a full‑week reward after depositing for only one second. It is subtle because the reward distribution appears correct for most users, and the edge case only manifests at the exact week boundary, making it easy to overlook in routine testing. From a user’s perspective the symptom is an unexpected increase in CANTO balance after a very short deposit, contradicting the expectation that rewards are earned only after a full week of participation. Conceptually, the bug belongs to the class of time‑bucket rounding errors where accounting periods are coarsely aligned, leading to inaccurate proportional calculations. The proper fix is to replace the week‑level truncation with a precise, per‑second accounting of deposit duration, or to split the epoch reward proportionally based on the actual fraction of the week the deposit was active, ensuring that rewards are truly time‑weighted and that no user can claim more than their real contribution warrants.
