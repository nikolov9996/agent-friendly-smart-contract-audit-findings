---
id: 7386
severity: "High"
---

# Ineffective ReserveRatio Enforcement

## Description

Per whitepaper, ReserveRatio ensures that some amount of pool liquidity is present in the contract at all times. This protects the pools from overutilization by strategists and ensures that a portion of the underlying pool assets are liquid so LPs can withdraw. If the ReserveRatio is set to 50, meaning 50% of a liquidity pool’s assets must remain in the pool at all times.

However, it was possible for the strategists to bypass the Reserve Ratio restriction and utilize all the funds in the pools, causing the pools to be illiquid.

Following are the impacts of this issue:

1. Underlying pool assets are overutilized by strategists, causing the pools to be illiquid. Users might not be able to withdraw their funds from the pools as the pools might not have sufficient underlying assets remained as their assets have been deployed to the Rubicon Market.
2. Reserve Ratio is one of the key security parameters to safeguard LP’s funds so that the amount of losses the pools could potentially incur is limited. Without effective reserve ratio enforcement, strategists could deploy (“invest”) all the user capital on the Rubicon Market. If the strategist makes a loss from all their orders, the LP would incur significant loss.

## Proof of Concept

Strategists place their market making trades via the `BathPair.placeMarketMakingTrades` function. This function would first check if the pool’s reserveRatio is maintained before proceeding. If true, strategists will be allowed to place their market making trades with orders with arbitrary pay amount. Strategists could place ask and bid orders with large pay amount causing large amount of funds to be withdrawn from the pools. The root cause is that at the end of the transaction, there is no additional validation to ensure the pools are not overutilized by strategists and the reserve ratio of the pools is maintained.

```solidity
function placeMarketMakingTrades(
    address[2] memory tokenPair, // ASSET, Then Quote
    uint256 askNumerator, // Quote / Asset
    uint256 askDenominator, // Asset / Quote
    uint256 bidNumerator, // size in ASSET
    uint256 bidDenominator // size in QUOTES
) public onlyApprovedStrategist(msg.sender) returns (uint256 id) {
    // Require at least one order is non-zero
    require(
        (askNumerator > 0 && askDenominator > 0) ||
            (bidNumerator > 0 && bidDenominator > 0),
        "one order must be non-zero"
    );

    address _underlyingAsset = tokenPair[0];
    address _underlyingQuote = tokenPair[1];

    (
        address bathAssetAddress,
        address bathQuoteAddress
    ) = enforceReserveRatio(_underlyingAsset, _underlyingQuote);

    require(
        bathAssetAddress != address(0) && bathQuoteAddress != address(0),
        "tokenToBathToken error"
    );
    .. SNIP..
    // Place new bid and/or ask
    // Note: placeOffer returns a zero if an incomplete order
    uint256 newAskID = IBathToken(bathAssetAddress).placeOffer(
        ask.pay_amt,
        ask.pay_gem,
        ask.buy_amt,
        ask.buy_gem
    );

    uint256 newBidID = IBathToken(bathQuoteAddress).placeOffer(
        bid.pay_amt,
        bid.pay_gem,
        bid.buy_amt,
        bid.buy_gem
    );
    .. SNIP..
}
```

```solidity
/// @notice This function enforces that the Bath House reserveRatio (a % of underlying pool liquidity) is enforced across all pools
/// @dev This function should ensure that reserveRatio % of the underlying liquidity always remains on the Bath Token. Utilization should be 1 - reserveRatio in practice assuming strategists use all available liquidity.
function enforceReserveRatio(
    address underlyingAsset,
    address underlyingQuote
)
    internal
    view
    returns (address bathAssetAddress, address bathQuoteAddress)
{
    bathAssetAddress = IBathHouse(bathHouse).tokenToBathToken(
        underlyingAsset
    );
    bathQuoteAddress = IBathHouse(bathHouse).tokenToBathToken(
        underlyingQuote
    );
    require(
        (
            IBathToken(bathAssetAddress).underlyingBalance().mul(
                IBathHouse(bathHouse).reserveRatio()
            )
        ).div(100) <= IERC20(underlyingAsset).balanceOf(bathAssetAddress),
        "Failed to meet asset pool reserve ratio"
    );
    require(
        (
            IBathToken(bathQuoteAddress).underlyingBalance().mul(
                IBathHouse(bathHouse).reserveRatio()
            )
        ).div(100) <= IERC20(underlyingQuote).balanceOf(bathQuoteAddress),
        "Failed to meet quote pool reserve ratio"
    );
}
```

The following is the snippet of the test case result. Reserve Ratio is initialized to 80% in this example, which means only 20% of the funds could be utilized by strategists. The BathWETH and BathDAI pools contained 1 WETH and 100 DAI respectively after users deposited their funds into the pools. At the bottom half of the output, it shows that it was possible for the strategists to utilise 90% of the funds in the pools to place an ask and bid order, which exceeded the 20% limit.

The last two lines of the output show that 90% of the funds in the pools are outstanding.

```solidity
..SNIP..
--------------- Order Book ---------------
[-] asks index 0: ask_pay_amt = 0, ask_buy_amt = 0
[-] asks index 1: ask_pay_amt = 0, ask_buy_amt = 0
[-] asks index 2: ask_pay_amt = 0, ask_buy_amt = 0
[-] asks index 3: ask_pay_amt = 0, ask_buy_amt = 0
[+] bids index 0: bid_pay_amt = 0, bid_buy_amt = 0
[+] bids index 1: bid_pay_amt = 0, bid_buy_amt = 0
[+] bids index 2: bid_pay_amt = 0, bid_buy_amt = 0
[+] bids index 3: bid_pay_amt = 0, bid_buy_amt = 0
bathAssetInstance: underlyingBalance() = 1 WETH, balanceOf = 1 WETH, Outstanding Amount = 0 WETH
bathQuoteInstance: underlyingBalance() = 100 DAI, balanceOf = 100 DAI, Outstanding Amount = 0 DAI
After Placing Order
--------------- Order Book ---------------
[-] asks index 0: ask_pay_amt = 0.9, ask_buy_amt = 180
[-] asks index 1: ask_pay_amt = 0, ask_buy_amt = 0
[-] asks index 2: ask_pay_amt = 0, ask_buy_amt = 0
[-] asks index 3: ask_pay_amt = 0, ask_buy_amt = 0
[+] bids index 0: bid_pay_amt = 90, bid_buy_amt = 0.9
[+] bids index 1: bid_pay_amt = 0, bid_buy_amt = 0
[+] bids index 2: bid_pay_amt = 0, bid_buy_amt = 0
[+] bids index 3: bid_pay_amt = 0, bid_buy_amt = 0
bathAssetInstance: underlyingBalance() = 1 WETH, balanceOf = 0.1 WETH, Outstanding Amount = 0.9 WETH
bathQuoteInstance: underlyingBalance() = 100 DAI, balanceOf = 10 DAI, Outstanding Amount = 90 DAI
..SNIP..
```

Test Script can be found at <https://gist.github.com/xiaoming9090/c4fcd4e967bd7d6940429e5d8e39004d>

## Recommendation

Check that the reserveRatio for each of the underlying liquidity pools (asset and quote bathTokens) is observed before and after function execution.

```solidity
function placeMarketMakingTrades(
    address[2] memory tokenPair, // ASSET, Then Quote
    uint256 askNumerator, // Quote / Asset
    uint256 askDenominator, // Asset / Quote
    uint256 bidNumerator, // size in ASSET
    uint256 bidDenominator // size in QUOTES
) public onlyApprovedStrategist(msg.sender) returns (uint256 id) {
    // Require at least one order is non-zero
    require(
        (askNumerator > 0 && askDenominator > 0) ||
            (bidNumerator > 0 && bidDenominator > 0),
        "one order must be non-zero"
    );

    address _underlyingAsset = tokenPair[0];
    address _underlyingQuote = tokenPair[1];

    (
        address bathAssetAddress,
        address bathQuoteAddress
    ) = enforceReserveRatio(_underlyingAsset, _underlyingQuote);

    require(
        bathAssetAddress != address(0) && bathQuoteAddress != address(0),
        "tokenToBathToken error"
    );
    .. SNIP..
    // Place new bid and/or ask
    // Note: placeOffer returns a zero if an incomplete order
    uint256 newAskID = IBathToken(bathAssetAddress).placeOffer(
        ask.pay_amt,
        ask.pay_gem,
        ask.buy_amt,
        ask.buy_gem
    );

    uint256 newBidID = IBathToken(bathQuoteAddress).placeOffer(
        bid.pay_amt,
        bid.pay_gem,
        bid.buy_amt,
        bid.buy_gem
    );
    .. SNIP..

    // Ensure that the strategist does not overutilize
    enforceReserveRatio(_underlyingAsset, _underlyingQuote);
}
```

Good issue! I believe it needs to just be moved to the end of the function. Nice catch and already implemented in practice.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an ineffective enforcement of the ReserveRatio invariant that is meant to keep a minimum proportion of a liquidity pool’s underlying assets on‑chain at all times. In the intended design, a ReserveRatio of 50 % means that at least half of the assets deposited by liquidity providers must remain in the pool so that users can withdraw their funds and the pool stays liquid. The contract implements a function called enforceReserveRatio that checks the ratio before a strategist executes market‑making trades via BathPair.placeMarketMakingTrades. However, the function is only called at the beginning of the transaction; after the strategist’s ask and bid orders are placed, the contract never re‑validates the invariant. Consequently, a strategist can specify large pay amounts in the orders, causing the BathToken balances to be drained far beyond the allowed limit. The pool’s underlyingBalance falls below the required reserve, making the pool effectively illiquid. Users attempting to withdraw later either receive zero tokens or experience a failed withdrawal because the underlying assets have been moved to the Rubicon Market. This leads to a loss of confidence for liquidity providers, who expect a guaranteed portion of their capital to be safely retained, and can cause significant financial loss if the strategist’s trades incur losses, as the entire user capital may have been exposed. The flaw was discovered during a security audit when test scripts showed that after a single call to placeMarketMakingTrades, the Outstanding Amount rose to 90 % of the pool, far exceeding the 20 % utilization permitted by an 80 % ReserveRatio. The issue is hard to notice because the pre‑trade check passes, no revert occurs, and the user interface may still display a normal pool balance while the internal accounting is violated. The bug belongs to the class of invariant‑violation or missing post‑condition checks, where the contract fails to enforce a critical business rule after state‑changing operations. To remediate, the reserve‑ratio check must be performed after the trade execution (or the function should be split into a pre‑check and a post‑check that reverts if the invariant is broken), ensuring that the pool cannot be over‑utilized. In conceptual terms, the fix restores the contract’s guarantee that a minimum reserve of assets is always present, preserving liquidity and protecting LP funds.
