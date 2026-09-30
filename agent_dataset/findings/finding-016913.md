---
id: 16913
severity: "High"
---

# `StandardPolicyERC1155.sol` returns `amount == 1` instead of `amount == order.amount`

## Description

[StandardPolicyERC1155.sol#L12-L36](https://github.com/code-423n4/2022-10-blur/blob/main/contracts/matchingPolicies/StandardPolicyERC1155.sol#L12-L36)  
[BlurExchange.sol#L154-L161](https://github.com/code-423n4/2022-10-blur/blob/main/contracts/BlurExchange.sol#L154-L161)  

The `canMatchMakerAsk` and `canMatchMakerBid` functions in `StandardPolicyERC1155.sol` will only return 1 as the amount instead of the order.amount value. This value is then used in the `_executeTokenTransfer` call during the execution flow and leads to only 1 ERC1155 token being sent. A buyer matching an ERC1155 order with amount > 1 would expect to receive amount of tokens if they pay the order’s price. The seller, who might also expect more than 1 tokens to be sent, would have set the order’s price to be for the amount of tokens and not just for 1 token.

The buyer would lose overspent ETH/WETH to the seller without receiving all tokens as specified in the order.

## Proof of Concept

[StandardPolicyERC1155.sol:canMatchMakerAsk](https://github.com/code-423n4/2022-10-blur/blob/main/contracts/matchingPolicies/StandardPolicyERC1155.sol#L12-L36)

```solidity
function canMatchMakerAsk(Order calldata makerAsk, Order calldata takerBid)
    external
    pure
    override
    returns (
        bool,
        uint256,
        uint256,
        uint256,
        AssetType
    )
{
    return (
        (makerAsk.side != takerBid.side) &&
        (makerAsk.paymentToken == takerBid.paymentToken) &&
        (makerAsk.collection == takerBid.collection) &&
        (makerAsk.tokenId == takerBid.tokenId) &&
        (makerAsk.matchingPolicy == takerBid.matchingPolicy) &&
        (makerAsk.price == takerBid.price),
        makerAsk.price,
        makerAsk.tokenId,
        1,
        AssetType.ERC1155
    );
}
```

The code above shows that `canMatchMakerAsk` only returns 1 as the amount. `_executeTokenTransfer` will then [call the executionDelegate’s `transferERC1155` function with only amount 1](https://github.com/code-423n4/2022-10-blur/blob/main/contracts/BlurExchange.sol#L540), transferring only 1 token to the buyer.

Test code added to `execution.test.ts`:

```solidity
it('Only 1 ERC1155 received for order with amount > 1', async () => {
  await mockERC1155.mint(alice.address, tokenId, 10);
  sell = generateOrder(alice, {
    side: Side.Sell,
    tokenId,
    amount: 10,
    collection: mockERC1155.address,
    matchingPolicy: matchingPolicies.standardPolicyERC1155.address,
  });
  buy = generateOrder(bob, {
    side: Side.Buy,
    tokenId,
    amount: 10,
    collection: mockERC1155.address,
    matchingPolicy: matchingPolicies.standardPolicyERC1155.address,
  });
  sellInput = await sell.pack();
  buyInput = await buy.pack();

  await waitForTx(exchange.execute(sellInput, buyInput));

  // Buyer only receives 1 token
  expect(await mockERC1155.balanceOf(bob.address, tokenId)).to.be.equal(1);
  await checkBalances(
    aliceBalance,
    aliceBalanceWeth.add(priceMinusFee),
    bobBalance,
    bobBalanceWeth.sub(price),
    feeRecipientBalance,
    feeRecipientBalanceWeth.add(fee),
  );
});
```

The test code above shows a sell order for an ERC1155 token with amount = 10 and a matching buy order. The `execute` function in `BlurExchange.sol` is called and the orders are matched but the buyer (bob) only receives 1 token instead of 10 despite paying the full price.

## Recommendation

Policies used for ERC1155 tokens should return and consider the amount of tokens set for the order.

This was an oversight on my part for not putting this contract as out-of-scope. Our marketplace does not handle ERC1155 yet and so we haven’t concluded what the matching criteria for those orders will be. This contract was mainly created to test ERC1155 transfers through the rest of the exchange, but shouldn’t be deployed initially. When we are prepared to handle ERC1155 orders we will have to develop a new matching policy that determines the amount from the order parameters. Acknowledging that it’s incorrect, but won’t be making any changes as the contract won’t be deployed.

The sponsor acknowledges the finding, and the report to be technically correct.  
However the sponsor claims they won’t be using the code in production.  

Because the code is technically incorrect and was in scope during the contest am going to assign High Severity.  
However, I do understand that the contract will not be deployed.

Despite the fact that some reports mention a slightly different risk than this one (mismatching amounts), given <https://github.com/code-423n4/org/issues/8> and given the consideration that these are substantially the same issue (the policy has a hardcoded amount), am going to group them under the same issue.

Because this report shows both sides of the issue, is well-written and has a coded Poc, am choosing to make it the selected report.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the matching policy contract used for ERC1155 orders within the Blur marketplace. The policy’s canMatchMakerAsk and canMatchMakerBid functions are designed to verify that a maker’s ask can be matched with a taker’s bid and to return the amount of tokens that should be transferred. However, both functions hard‑code the returned amount to the constant value 1 instead of forwarding the amount that was specified in the order (makerAsk.amount or takerBid.amount). This discrepancy originates from an oversight in the policy implementation: the code checks that the sides, payment token, collection, tokenId, matching policy and price all match, but it unconditionally returns 1 for the amount field in the tuple that is later consumed by the exchange’s execution routine. When the exchange’s _executeTokenTransfer routine receives this hard‑coded amount, it invokes the ERC1155 transfer function with a quantity of 1, regardless of how many tokens the seller intended to sell. Consequently, a buyer who places a bid for, for example, 10 ERC1155 tokens and pays the full price for those 10 tokens will only receive a single token. The seller, who set the order price based on delivering 10 tokens, will nonetheless collect the full payment, effectively receiving payment for nine tokens that never reach the buyer. From the user’s perspective the symptoms are stark: the buyer’s wallet shows the correct ETH/WETH deduction, yet the ERC1155 balance for the purchased token ID increases by only one instead of the expected ten, appearing as a missing or zero‑balance error for the remaining units. The issue is triggered whenever an order involving ERC1155 assets specifies an amount greater than one and is matched using the StandardPolicyERC1155 contract. It affects all participants in the marketplace – buyers, sellers, and the protocol itself – because it undermines the fundamental accounting guarantees of the exchange: payment should be proportional to the quantity delivered. The problem was discovered during a security audit that included functional tests; a test case explicitly minted ten tokens to the seller, created matching sell and buy orders with amount 10, executed the trade, and observed that only one token was transferred. The bug can be difficult to notice in production because the contract currently does not support ERC1155 orders, so the faulty policy is not actively used, and the mismatch only surfaces when amounts exceed one. To remediate the issue, the matching policy must be rewritten to return the actual amount from the order parameters instead of a constant, and the overall design should ensure that any future ERC1155 matching logic correctly propagates the requested quantity through all execution paths. In abstract terms, this is a hard‑coded value bug that violates the invariant that transferred token quantity equals the order‑specified amount, leading to financial loss and breach of trust in the marketplace’s accounting logic.
