---
id: 22415
severity: "High"
---

# Users can deposit "0" ether to any round

## Description

The main invariant to determine the winner is that the indexes must be in ascending order with no repetitions. Therefore, depositing "0" is strictly prohibited as it does not increase the index. However, there is a method by which a user can easily deposit "0" ether to any round without any extra costs than gas. As stated in the summary, depositing "0" will not increment the entryIndex, leading to a potential issue with the indexes array. This, in turn, may result in an unfair winner selection due to how the upper bound is determined in the array. The relevant code snippet illustrating this behavior is found here.

Let's check the following code snippet in the depositETHIntoMultipleRounds function:
```solidity
for (uint256 i; i < numberOfRounds; ++i) {
    uint256 roundId = _unsafeAdd(startingRoundId, i);
    Round storage round = rounds[roundId];
    uint256 roundValuePerEntry = round.valuePerEntry;
    if (roundValuePerEntry == 0) {
        (, , roundValuePerEntry) = _writeDataToRound({roundId: roundId,
        roundValue: 0});
    }
    _incrementUserDepositCount(roundId, round);
    // @review depositAmount can be "0"
    uint256 depositAmount = amounts[i];
    // @review 0 % ANY_NUMBER = 0
    if (depositAmount % roundValuePerEntry != 0) {
        revert InvalidValue();
    }
    uint256 entriesCount = _depositETH(round, roundId,
    roundValuePerEntry, depositAmount);
    expectedValue += depositAmount;
    entriesCounts[i] = entriesCount;
}
// @review will not fail as long as user deposits normally to 1 round
// then he can deposit to any round with "0" amounts
if (expectedValue != msg.value) {
    revert InvalidValue();
}
```
explains how its possible. As long as user deposits normally to 1 round then he can also deposit "0" amounts to any round because the expectedValue will be equal to msg.value.

Textual PoC: Assume Alice sends the tx with 1 ether as msg.value and "amounts" array as [1 ether, 0, 0]. first time the loop starts the 1 ether will be correctly evaluated in to the round. When the loop starts the 2nd and 3rd iterations it won't revert because the following code snippet will be "0" and adding 0 to expectedValue will not increment to expectedValue so the msg.value will be exactly same with the expectedValue.
```solidity
if (depositAmount % roundValuePerEntry != 0) {
    revert InvalidValue();
}
```
Coded PoC (copy the test to Yolo.deposit.sol file and run the test):
```solidity
function test_deposit0ToRounds() external {
    vm.deal(user2, 1 ether);
    vm.deal(user3, 1 ether);
    // @dev first round starts normally
    vm.prank(user2);
    yolo.deposit{value: 1 ether}(1, _emptyDepositsCalldata());
    // @dev user3 will deposit 1 ether to the current round(1) and will deposit
    // 0,0 to round 2 and round3
    uint256[] memory amounts = new uint256[](3);
    amounts[0] = 1 ether;
    amounts[1] = 0;
    amounts[2] = 0;
    vm.prank(user3);
    yolo.depositETHIntoMultipleRounds{value: 1 ether}(amounts);
    // @dev check user3 indeed managed to deposit 0 ether to round2
    IYoloV2.Deposit[] memory deposits = _getDeposits(2);
    assertEq(deposits.length, 1);
    IYoloV2.Deposit memory deposit = deposits[0];
    assertEq(uint8(deposit.tokenType), uint8(IYoloV2.YoloV2__TokenType.ETH));
    assertEq(deposit.tokenAddress, address(0));
    assertEq(deposit.tokenId, 0);
    assertEq(deposit.tokenAmount, 0);
    assertEq(deposit.depositor, user3);
    assertFalse(deposit.withdrawn);
    assertEq(deposit.currentEntryIndex, 0);
    // @dev check user3 indeed managed to deposit 0 ether to round3
    deposits = _getDeposits(3);
    assertEq(deposits.length, 1);
    deposit = deposits[0];
    assertEq(uint8(deposit.tokenType), uint8(IYoloV2.YoloV2__TokenType.ETH));
    assertEq(deposit.tokenAddress, address(0));
    assertEq(deposit.tokenId, 0);
    assertEq(deposit.tokenAmount, 0);
    assertEq(deposit.depositor, user3);
    assertFalse(deposit.withdrawn);
    assertEq(deposit.currentEntryIndex, 0);
}
```
High, since it will alter the games winner selection and it is very cheap to perform the attack.

## Proof of Concept

no poc

## Recommendation

Add the following check inside the depositETHIntoMultipleRounds function:
```solidity
if (depositAmount == 0) {
    revert InvalidValue();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of allowing a participant to submit a deposit of zero ether to any round through the depositETHIntoMultipleRounds function. The contract assumes that each deposit increases the round's entry index, which is used as a strictly increasing, non‑repeating identifier for entries and as the basis for determining the winner. Because the code only checks that the deposit amount is a multiple of the round's value per entry, a zero amount passes the modulo test (0 % X == 0) and the subsequent check that the sum of deposited amounts equals msg.value also passes, since adding zero does not change the accumulated expectedValue. Consequently the internal entryIndex for the zero‑value deposit remains unchanged (typically zero), breaking the invariant that indexes must be unique and ordered. An attacker can first make a normal deposit to a round, then include additional zero‑value entries for other rounds in the same transaction. These zero entries are recorded with the same entry index as previous entries, which can distort the calculation of the upper bound used in winner selection, potentially allowing the attacker to influence or manipulate the outcome of the game. From a user’s perspective the UI may show a successful deposit with a zero amount, no balance change, and the deposit appears in the round’s list, but the protocol’s accounting assumes each entry contributes to the ordering logic, leading to an unfair winner selection. The issue was discovered during a manual audit and reproduced with a test that sent 1 ether and an amounts array of [1 ether, 0, 0], confirming that the contract accepted the zero deposits without reverting. The bug is subtle because zero‑value operations are often considered no‑ops and do not emit obvious error messages, making it easy to overlook during functional testing. The proper remediation is to enforce that depositAmount must be greater than zero before proceeding, thereby preserving the monotonic index invariant and preventing manipulation of the winner selection algorithm.
