---
id: 21561
severity: "High"
---

# Math error in creator payment calculation

## Description

The Tunnl protocol applies 3 kinds of fees.
- **Flat Fee**: The advertiser pays a flat fee and it is charged on acceptance of offers.
- **Advertiser Percentage Fee**: The advertiser percentage fee is the percentage fee that is charged to the advertiser. It is an extra amount added to the offer value.
- **Creator Percentage Fee**: The creator percentage fee is the percentage fee that is charged to the creator. It is charged based on the amount the creator is paid.

The advertisers create offers starting from a maximum offer amount $maxOfferAmount$ and the total amount including all posssible fees are calculated as $maxOfferAmount * (1 + advertiserFee)+flatFee$.
This amount is stored in the `Offer::maxValueUsdc` and used in many places for accounting.

After a successful verification, `TunnlTwitterOffers::sendFunctionsRequest()` is called to get the actual amount that should be paid to the creator.
This function calls a function `FunctionClient::_sendRequest()` with the request and the maximum offer amount is encoded in the request arguments.
But in the calculation of `maxCreatorPayment`, `s_config.creatorFeePercentageBP` is used instead of `s_config.advertiserFeePercentageBP`.

```solidity
uint256 maxCreatorPayment = uint256((s_offers[offerId].maxValueUsdc - s_offers[offerId].flatFeeUsdc) * 10000)
    / uint256(10000 + s_config.creatorFeePercentageBP);//@audit-issue this should be 10000+s_config.advertiserFeePercentageBP

console.log("maxCreatorPayment: %s", maxCreatorPayment);//@audit-info

bytes[] memory bytesArgs = new bytes[](4);
bytesArgs[0] = abi.encode(offerId);
bytesArgs[1] = abi.encodePacked(s_offers[offerId].creationDate);
bytesArgs[2] = abi.encodePacked(maxCreatorPayment);//@audit-info maximum offer amount relayed
bytesArgs[3] = abi.encodePacked(s_offers[offerId].offerDurationSeconds);
req.setBytesArgs(bytesArgs);

bytes32 requestId = _sendRequest(
    req.encodeCBOR(),
    s_config.functionsSubscriptionId,
    s_config.functionsCallbackGasLimit,
    s_config.functionsDonId
);
```

The current implementation does not change the payment according to the performance of the content (e.g. likes, views, ... ) and the relayed maximum amount is fully paid to the creator. Hence, the final payment to the creator is being wrong.

This error can lead to two kinds of problems.
- If `creatorFeePercentageBP<advertiserFeePercentageBP`, `maxCreatorPayment` becomes larger than the actual maximum offered amount and the payment distribution in the function `TunnlTwitterOffers::fulfillRequest` will revert with `Exceeds max` error.
- If `creatorFeePercentageBP>advertiserFeePercentageBP`, `maxCreatorPayment` becomes less than the actual maximum offered amount and the creator gets paid less amount.

Note that the current test suite belongs to the first case but the errors are not caught because request fulfillment is simulated with an artificial value rather than the actual value that is set by the nodes using the `calculatepayment.js` script.

```solidity
function test_PayOut() public {
    // Define the amount to be paid in USDC
    uint256 amountPaidUsdc = uint256(uint256(100e6));
    test_Verification_Success();
    // Warp time for payout and perform Chainlink automation
    vm.warp(block.timestamp + (1 weeks - 100));
    performUpkeep();
    // Fulfill request for payout  with PayOutamount
    mockFunctionsRouter.fulfill(
        address(tunnlTwitterOffers),
        functionsRequestIds[offerId],
        abi.encode(amountPaidUsdc),//@audit-info should be same to the maxCreatorPayout in the current implementation
        ""
    );

    // Assert balances after payout
    assertEq(mockUsdcToken.balanceOf(advertiser), 0);
    assertEq(mockUsdcToken.balanceOf(address(tunnlTwitterOffers)), (0));
    assertEq(
        mockUsdcToken.balanceOf(contentCreator),
        amountPaidUsdc - (amountPaidUsdc * tunnlTwitterOffers.getConfig().creatorFeePercentageBP) / 10000
    );
}
```

We evaluate the impact to be CRITICAL because the protocol will not function at all or the creator gets less amount than offered systematically.

## Proof of Concept

Because it is not easy to check the actual `maxCreatorPayment` value that is set as a request argument, we inserted a line to log its value in the function `TunnlTwitterOffers::sendFunctionsRequest()`.

```solidity
console.log("maxCreatorPayment: %s", maxCreatorPayment);
```

Running the test case `test_PayOut()` outputs as below.

```bash
[PASS] test_PayOut() (gas: 531524)
Logs:
  100000000 110000000 <- Max offered amount and maxValueUsdc
  maxCreatorPayment: 102439024 <- This must be the same to the offered amount 100e6
  maxCreatorPayment: 102439024
```

## Recommendation

Fix the `sendFunctionsRequest()` function as below. Note that the team reported another issue in using the fee percentage value from `s_config` instead of the `s_offers[offerId]` and the mitigiation below reflects that as well.

```diff
uint256 maxCreatorPayment = uint256((s_offers[offerId].maxValueUsdc - s_offers[offerId].flatFeeUsdc) * 10000)//@audit-info why not use the percentage directly - (s_offers[offerId].maxValueUsdc - s_offers[offerId].flatFeeUsdc) * (10000 - s_config.creatorFeePercentageBP) / 10000
--          / uint256(10000 + s_config.creatorFeePercentageBP);
++          / uint256(10000 + s_offers[offerId].advertiserFeePercentageBP);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mathematical error in the calculation of the maximum amount that can be paid to a content creator in the Tunnl protocol. The contract stores the total offer value as maxValueUsdc, which already includes a flat fee and an advertiser percentage fee. When the protocol prepares a Chainlink Functions request it derives maxCreatorPayment by subtracting the flat fee and then dividing by 10000 plus s_config.creatorFeePercentageBP. The intended denominator should be 10000 plus the advertiser fee percentage that belongs to the specific offer (s_offers[offerId].advertiserFeePercentageBP). By using the creator fee percentage instead, the contract either inflates the payable amount when the creator fee is lower than the advertiser fee, causing the fulfillment logic to revert with an “Exceeds max” error, or deflates the amount when the creator fee is higher, resulting in the creator receiving less than the advertised amount. This mis‑calculation occurs every time sendFunctionsRequest() is called, i.e., after a successful verification of an offer, and it is hidden because the value is only logged and the test suite supplies a mocked fulfillment amount that does not reflect the real maxCreatorPayment. The bug affects advertisers who expect their full budget to be spent, creators who expect to receive the promised payment, and the protocol itself because payouts may fail or be systematically under‑paid, breaking the economic model. The issue was discovered during a manual audit by Cyfrin, which noticed the wrong configuration variable being used and confirmed the problem by logging the computed maxCreatorPayment. It is hard to notice because the incorrect value is not compared against the stored maxValueUsdc and the existing unit tests use an artificial payout amount, so the discrepancy does not surface in the test run. The vulnerability belongs to the class of fee‑calculation bugs where an incorrect percentage is applied in an arithmetic expression, leading to wrong accounting and potential loss of funds. From a user’s perspective the creator may see a zero or reduced balance after a payout, the advertiser may see leftover funds or a transaction revert, and the UI may show a successful campaign while no funds are actually transferred. The correct fix is to replace s_config.creatorFeePercentageBP with the advertiser fee percentage stored in the offer (s_offers[offerId].advertiserFeePercentageBP) and to compute the payment using the proper formula that subtracts the creator fee after the advertiser fee has been accounted for. This change restores the intended accounting logic, ensures that the maximum creator payment never exceeds the offer budget, and prevents under‑payment of creators.
