---
id: 3961
severity: "High"
---

# Buyer can request randomness multiple times

## Description

To participate in LotteryV2 the ticket buyer calls LotteryV2Base::deposit. This will trigger a randomness request to the VRF:
```solidity
function deposit(uint256 amount) public lotteryStarted hasNotWonInLotteryV1(_msgSender()) {
    require(amount > 0, "No funds sent");
    if (rolledNumbers[_msgSender()] == 0) {
        _requestRandomness(abi.encode(_msgSender()));
        emit RandomRequested(_msgSender());
    }
}
```
This randomness request is later processed by the VRF in LotteryV2Base::_fulfillRandomness, where on line 142 the number is checked against the winning number:
```solidity
function _fulfillRandomness(uint256 randomness, uint256, bytes memory extraData) internal override {
    uint256 _randomNumber = DigitExtractor.extractFirst14Digits(randomness);
    if (requestedBy == seller) {
        randomNumber = _randomNumber;
    } else {
        rolledNumbers[requestedBy] = _randomNumber;
        claimNumber(requestedBy);
    }
    emit RandomFullfiled(requestedBy, _randomNumber);
}
```
The issue here is that in deposit it only checks that the user doesn't have a fulfilled request. VRFs take some time to process requests. A ticket buyer could send as many requests as they can before the first one is fulfilled which will increase their changes to win. Since as long as one of the rolls succeed they'll get added to the winners list. Only the first one need to be above the minimum deposit threshold, the later ones can just be dust. Hence a buyer could get many rolls for just one ticket price.

## Proof of Concept

```solidity
function test_LotteryV2RequestRandomnessMultipleTimesDeposit() public {
    usdc.mint(alice, 2e6);
    vm.startPrank(alice);
    // first randomness request with enough to cover minimum deposit
    bytes memory data = abi.encode(0, abi.encode(alice));
    uint256 round = _round();
    bytes memory dataWithRound = abi.encode(round, data);
    emit IGelatoVRFConsumer.RequestedRandomness(round, data);
    lottery.deposit(1e6);
    // second randomness request while first is still pending for dust
    data = abi.encode(1, abi.encode(alice));
    dataWithRound = abi.encode(round, data);
    emit IGelatoVRFConsumer.RequestedRandomness(round, data);
    lottery.deposit(1);
    vm.stopPrank();
}
```
Please find the full test setup here

## Recommendation

Consider only sending a randomness request if both rolledNumbers[_msgSender()] == 0 and deposits[_msgSender()] == 0 in both LotteryV2Base::deposit and transferDeposit:
```solidity
if (deposits[_msgSender()] == 0) {
    participants.push(_msgSender());
    if (rolledNumbers[_msgSender()] == 0) {
        _requestRandomness(abi.encode(_msgSender()));
        emit RandomRequested(_msgSender());
    }
}
deposits[_msgSender()] += amount;
```
This will guarantee that only one request is sent per ticket buyer.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability allows a lottery participant to obtain multiple independent randomness draws for the price of a single ticket, thereby inflating their probability of winning. The contract’s deposit function only verifies that the caller’s rolled number is zero before issuing a VRF request, but it does not check whether a randomness request is already pending or whether the caller has already recorded a deposit. Because the VRF service processes requests asynchronously, an attacker can submit several deposit transactions in rapid succession while the first request is still awaiting fulfillment. Each deposit, even with a dust amount, triggers a new _requestRandomness call, resulting in multiple random numbers being stored for the same participant when the VRF callbacks are finally executed. The attacker’s multiple rolls are all evaluated against the winning number, and any successful roll adds the attacker to the winners list, effectively granting them many tickets for a single payment. This breaks the core business rule that each ticket costs a fixed amount and yields exactly one draw, leading to an unfair advantage, reduced expected returns for honest participants, and potential loss of revenue for the protocol. The issue manifests when the VRF latency is non‑zero and the contract does not maintain a flag for pending requests. From a user’s perspective the UI may indicate that a single ticket was purchased, yet the backend records several entries, causing unexpected wins or, conversely, other users seeing their odds diminish. The flaw was discovered during a security audit that examined state checks around the randomness request logic; it is subtle because the contract emits the usual events and does not revert, making the extra draws invisible to casual observers. The bug belongs to the class of insufficient state validation and request replay vulnerabilities, where a function can be called repeatedly before a prior asynchronous operation completes. To remediate, the contract should enforce that a randomness request is sent only when both the participant’s rolled number and deposit balance are zero, or maintain an explicit pending‑request flag, ensuring exactly one draw per ticket purchase.
