---
id: 18414
severity: "High"
---

# `InitialETHCrowdfund` + `ReraiseETHCrowdfund`: `batchContributeFor` function may not refund ETH which leads to loss of funds

## Description

This vulnerability exists in both the [`InitialETHCrowdfund`](https://github.com/code-423n4/2023-04-party/blob/main/contracts/crowdfund/InitialETHCrowdfund.sol) and [`ReraiseETHCrowdfund`](https://github.com/code-423n4/2023-04-party/blob/main/contracts/crowdfund/ReraiseETHCrowdfund.sol) contracts in exactly the same way.

I will continue this report by explaining the issue in only one contract. The mitigation section however contains the fix for both instances.

The [`batchContributeFor`](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/InitialETHCrowdfund.sol#L235-L268) function is a wrapper that allows to make multiple calls to `contributeFor` within one function call.

It is possible to specify that this function should not revert when one individual call to `contributeFor` fails by setting `args.revertOnFailure=false`.

The issue is that in this case the ETH for a failed contribution is not refunded which leads a loss of funds for the user calling the function.

Note:  
This issue also exists in the [`Crowdfund.batchContributeFor`](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/Crowdfund.sol#L367-L385) function which is out of scope. The sponsor knows about this and will fix it.

## Proof of Concept

Let’s look at the `batchContributeFor` function:
```solidity
function batchContributeFor(
    BatchContributeForArgs calldata args
) external payable onlyDelegateCall returns (uint96[] memory votingPowers) {
    uint256 numContributions = args.recipients.length;
    votingPowers = new uint96[](numContributions);

    uint256 ethAvailable = msg.value;
    for (uint256 i; i < numContributions; ++i) {
        ethAvailable -= args.values[i];

        (bool s, bytes memory r) = address(this).call{ value: args.values[i] }(
            abi.encodeCall(
                this.contributeFor,
                (
                    args.tokenIds[i],
                    args.recipients[i],
                    args.initialDelegates[i],
                    args.gateDatas[i]
                )
            )
        );

        if (!s) {
            if (args.revertOnFailure) {
                r.rawRevert();
            }
        } else {
            votingPowers[i] = abi.decode(r, (uint96));
        }
    }

    // Refund any unused ETH.
    if (ethAvailable > 0) payable(msg.sender).transfer(ethAvailable);
}
```

We can see that `ethAvailable` is reduced before every call to `contributeFor`:
```solidity
ethAvailable -= args.values[i];
```

But it is only checked later if the call was successful:
```solidity
if (!s) {
    if (args.revertOnFailure) {
        r.rawRevert();
    }
```

And if `args.revertOnFailure=false` there is no revert and `ethAvailable` is not increased again.

Therefore the user has to pay for failed contributions.

Add the following test to the `InitialETHCrowdfund.t.sol` test file:
```solidity
function test_batchContributeFor_noETHRefund() public {
    InitialETHCrowdfund crowdfund = _createCrowdfund({
        initialContribution: 0,
        initialContributor: payable(address(0)),
        initialDelegate: address(0),
        minContributions: 1 ether,
        maxContributions: type(uint96).max,
        disableContributingForExistingCard: false,
        minTotalContributions: 3 ether,
        maxTotalContributions: 5 ether,
        duration: 7 days,
        fundingSplitBps: 0,
        fundingSplitRecipient: payable(address(0))
    });
    Party party = crowdfund.party();

    address sender = _randomAddress();
    vm.deal(sender, 2.5 ether);

    // Batch contribute for
    vm.prank(sender);
    uint256[] memory tokenIds = new uint256[](3);
    address payable[] memory recipients = new address payable[](3);
    address[] memory delegates = new address[](3);
    uint96[] memory values = new uint96[](3);
    bytes[] memory gateDatas = new bytes[](3);
    for (uint256 i; i < 3; ++i) {
        recipients[i] = _randomAddress();
        delegates[i] = _randomAddress();
        values[i] = 1 ether;
    }

    // @audit-info set values[2] = 0.5 ether such that contribution fails (minContribution = 1 ether)
    values[2] = 0.5 ether;

    uint96[] memory votingPowers = crowdfund.batchContributeFor{ value: 2.5 ether }(
        InitialETHCrowdfund.BatchContributeForArgs({
            tokenIds: tokenIds,
            recipients: recipients,
            initialDelegates: delegates,
            values: values,
            gateDatas: gateDatas,
            revertOnFailure: false
        })
    );

    // @audit-info balance of sender is 0 ETH even though 0.5 ETH of the 2.5 ETH should have been refunded
    assertEq(address(sender).balance, 0 ether);
}
```

The `sender` sends 2.5 ETH and 1 of the 3 contributions fails since `minContribution` is above the amount the `sender` wants to contribute (Note that in practice there are more ways for the contribution to fail).

The sender’s balance in the end is 0 ETH which shows that there is no refund.

## Recommendation

The following changes need to be made to the `InitialETHCrowdfund` and `ReraiseETHCrowdfund` contracts:
```diff
diff --git a/contracts/crowdfund/InitialETHCrowdfund.sol b/contracts/crowdfund/InitialETHCrowdfund.sol
index 8ab3b5c..19e09ac 100644
--- a/contracts/crowdfund/InitialETHCrowdfund.sol
+++ b/contracts/crowdfund/InitialETHCrowdfund.sol
@@ -240,8 +240,6 @@ contract InitialETHCrowdfund is ETHCrowdfundBase {

        uint256 ethAvailable = msg.value;
        for (uint256 i; i < numContributions; ++i) {
-            ethAvailable -= args.values[i];
-
            (bool s, bytes memory r) = address(this).call{ value: args.values[i] }(
                abi.encodeCall(
                    this.contributeFor,
@@ -260,6 +258,7 @@ contract InitialETHCrowdfund is ETHCrowdfundBase {
                }
            } else {
                votingPowers[i] = abi.decode(r, (uint96));
+               ethAvailable -= args.values[i];
            }
        }

diff --git a/contracts/crowdfund/ReraiseETHCrowdfund.sol b/contracts/crowdfund/ReraiseETHCrowdfund.sol
index 580623d..ad70b27 100644
--- a/contracts/crowdfund/ReraiseETHCrowdfund.sol
+++ b/contracts/crowdfund/ReraiseETHCrowdfund.sol
@@ -179,8 +179,6 @@ contract ReraiseETHCrowdfund is ETHCrowdfundBase, CrowdfundNFT {

        uint256 ethAvailable = msg.value;
        for (uint256 i; i < numContributions; ++i) {
-            ethAvailable -= args.values[i];
-
            (bool s, bytes memory r) = address(this).call{ value: args.values[i] }(
                abi.encodeCall(
                    this.contributeFor,
@@ -194,6 +192,7 @@ contract ReraiseETHCrowdfund is ETHCrowdfundBase, CrowdfundNFT {
                }
            } else {
                votingPowers[i] = abi.decode(r, (uint96));
+               ethAvailable -= args.values[i];
            }
        }
```

Now `ethAvailable` is only reduced when the call to `contributeFor` was successful.

Would welcome comment on this issue. AFAICT, this leads to a direct loss of user funds, which makes me think that a High severity is warranted. There is no external pre-condition(s) required for this to happen.

@0xean - Yeah you are right, it leads to a direct loss of funds and there are no preconditions. Should have set it to “High” probably.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the batchContributeFor wrapper used by both the InitialETHCrowdfund and ReraiseETHCrowdfund contracts. The function is designed to forward a series of individual contributeFor calls while tracking the amount of ether that remains available for refund. The implementation subtracts the intended contribution amount from the local ethAvailable variable before each call, regardless of whether the call succeeds. When a contribution fails and the caller has set the revertOnFailure flag to false, the function does not revert the transaction and also does not restore the deducted amount to ethAvailable. Consequently, the final refund step only returns the ether that remained after the premature deductions, leaving the failed contribution amount permanently lost to the caller. The root cause is an accounting error: the contract assumes that all forwarded ether will be consumed, but it fails to roll back the accounting state on partial failure. An attacker or a careless user can trigger the bug by including at least one contribution that violates the minimum contribution requirement or any other condition that makes contributeFor revert, while explicitly disabling automatic reverts. Under these conditions the transaction appears successful, no error is emitted, but the caller’s balance is reduced by the amount of the failed contribution. The impact is a direct loss of user funds; the user may see their wallet balance drop unexpectedly, often to zero, even though the transaction receipt shows success. The issue affects any participant who uses batchContributeFor with revertOnFailure set to false, as well as the overall protocol because the accounting of total contributions becomes inaccurate. It was discovered during a security audit when a test case demonstrated that a sender who supplied 2.5 ether and included a failing contribution ended with a zero ether balance. The bug is subtle because the contract does not emit a revert or explicit error, making the loss appear as a silent shortfall rather than a failed transaction. The class of bug is an improper handling of partial failures in batch operations, specifically a refund logic error where deducted funds are not restored on failure. To remediate, the contract should only decrement ethAvailable after a successful contribution or should add the amount back to ethAvailable when a call fails, ensuring that any unused ether is correctly refunded to the caller. This change restores the intended accounting guarantees and prevents silent loss of funds.
