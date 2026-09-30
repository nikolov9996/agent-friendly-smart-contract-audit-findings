---
id: 18410
severity: "High"
---

# Users wouldn’t refund from the lost ETH crowdfunds due to the lack of ETH

## Description

After the ETH crowdfunds are lost, contributors wouldn’t refund their funds because the crowdfund contract doesn’t have enough ETH balance.

## Proof of Concept

The core flaw is `_calculateRefundAmount()` might return more refund amount than the original contribution amount.

```solidity
    function _calculateRefundAmount(uint96 votingPower) internal view returns (uint96 amount) {
        amount = (votingPower * 1e4) / exchangeRateBps;

        // Add back fee to contribution amount if applicable.
        address payable fundingSplitRecipient_ = fundingSplitRecipient;
        uint16 fundingSplitBps_ = fundingSplitBps;
        if (fundingSplitRecipient_ != address(0) && fundingSplitBps_ > 0) {
            amount = (amount * 1e4) / (1e4 - fundingSplitBps_); // @audit might be greater than original contribution
        }
    }
```

When users contribute to the ETH crowdfunds, it subtracts the fee from the contribution amount.

    File: 2023-04-party\contracts\crowdfund\ETHCrowdfundBase.sol
    226:         uint16 fundingSplitBps_ = fundingSplitBps;
    227:         if (fundingSplitRecipient_ != address(0) && fundingSplitBps_ > 0) {
    228:             uint96 feeAmount = (amount * fundingSplitBps_) / 1e4;
    229:             amount -= feeAmount;
    230:         }

During the calculation, it calculates `feeAmount` first which is rounded down and subtracts from the contribution amount. It means the final amount after subtracting the fee would be rounded up.

So when we calculate the original amount using `_calculateRefundAmount()`, we might get a greater value.

This shows the detailed example and POC.

  1. Let’s assume `fundingSplitBps = 1e3(10%), exchangeRateBps = 1e4`.
  2. A user contributed `1e18 - 1` wei of ETH. After subtracting the fee, the voting power was `1e18 - 1 - (1e18 - 1) / 10 = 9 * 1e17`
  3. Let’s assume there are no other contributors and the crowdfund was lost.
  4. When the user calls `refund()`, the refund amount will be `9 * 1e17 * 1e4 / 9000 = 1e18` in `_calculateRefundAmount()`
  5. So it will try to transfer 1e18 wei of ETH from the crowdfund contract that contains 1e18 - 1 wei only. As a result, the transfer will revert and the user can’t refund his funds.

```solidity
        function test_refund_reverts() public {
            InitialETHCrowdfund crowdfund = _createCrowdfund({
                initialContribution: 0,
                initialContributor: payable(address(0)),
                initialDelegate: address(0),
                minContributions: 0,
                maxContributions: type(uint96).max,
                disableContributingForExistingCard: false,
                minTotalContributions: 3 ether,
                maxTotalContributions: 5 ether,
                duration: 7 days,
                fundingSplitBps: 1000, //10% fee
                fundingSplitRecipient: payable(_randomAddress()) //recipient exists
            });
            Party party = crowdfund.party();

            uint256 ethAmount = 1 ether - 1; //contribute amount

            address member = _randomAddress();
            vm.deal(member, ethAmount);

            // Contribute
            vm.prank(member);
            crowdfund.contribute{ value: ethAmount }(member, "");
            assertEq(address(member).balance, 0);
            assertEq(address(crowdfund).balance, ethAmount); //crowdfund's balance = 1 ether - 1

            skip(7 days);

            assertTrue(crowdfund.getCrowdfundLifecycle() == ETHCrowdfundBase.CrowdfundLifecycle.Lost);

            // Claim refund
            vm.prank(member);
            uint256 tokenId = 1;
            crowdfund.refund(tokenId); //reverts as it tried to withdraw 1 ether
        }
```

## Recommendation

When we subtract the fee in [_processContribution()](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ETHCrowdfundBase.sol#L227), we should calculate the final amount using `1e4 - fundingSplitBps` directly. Then there will be 2 rounds down in `_processContribution()` and `_calculateRefundAmount` and the refund amount won’t be greater than the original amount.

```solidity
    if (fundingSplitRecipient_ != address(0) && fundingSplitBps_ > 0) {
        amount = (amount * (1e4 - fundingSplitBps_)) / 1e4;
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a refund‑calculation error in the ETH crowdfund contract that can cause the contract to attempt to transfer more ether than it actually holds, causing the refund transaction to revert and leaving contributors unable to retrieve their funds. The root cause is a mismatch in rounding direction when the contract subtracts a funding‑split fee from a contribution and later adds the fee back during refund calculation. During contribution the fee amount is computed with integer division, which rounds down, and the net contribution is therefore rounded up. When a refund is processed the _calculateRefundAmount function multiplies the stored voting power by a factor and then divides by (1e4‑fundingSplitBps), effectively rounding up the fee component. This second rounding can produce a refund amount that is slightly larger than the original contribution, for example by one wei. When the crowdfund enters the Lost state and a contributor calls refund, the contract tries to send the inflated amount. Because the contract balance is only the actual contributed amount (which is lower by the rounding discrepancy), the transfer fails and the transaction reverts. The impact is that users see their refund calls revert, receive no ether, and their balances remain unchanged, contrary to the expectation that they would get back the exact amount they contributed. The issue occurs only when a funding split fee is configured (fundingSplitBps > 0) and the crowdfund has been marked as Lost, but it can affect any contributor because the rounding error is deterministic for the given fee percentage. The bug was discovered during a security audit that included a concrete test case reproducing the revert with a contribution of 1 ether‑1 wei and a 10 % fee. The problem is subtle because the contract’s balance appears correct at a glance, and the off‑by‑one error is hidden in integer arithmetic, making it hard to notice without precise accounting checks. To fix the issue the refund calculation should use the same rounding direction as the contribution subtraction, for example by applying the fee factor as amount * (1e4‑fundingSplitBps) / 1e4 when processing contributions and avoiding a second division that can round up. This ensures that the computed refund never exceeds the original contribution, preventing the contract from attempting to transfer more ether than it holds and restoring reliable refund behavior. The vulnerability belongs to the class of rounding‑error and accounting‑logic bugs that break financial invariants in smart contracts, leading to lost or locked funds and violating the protocol’s guarantee that contributors can retrieve their deposits after a failed crowdfund.
