---
id: 22648
severity: "High"
---

# Overflow in curate() function, results in per-

## Description

The Axis-Finance protocol has a curate() function that can be used to set a certain fee to a curator set by the seller for a certain auction. Typically, a curator is providing some service to an auction seller to help the sale succeed. This could be doing diligence on the project and vouching for them, or something simpler, such as listing the auction on a popular interface. A lot of memecoins have a big supply in the trillions, for example SHIBA INU has a total supply of nearly 1000 trillion tokens and each token has 18 decimals. With a lot of new memecoins emerging every day due to the favorable bullish conditions and having supply in the trillions, it is safe to assume that such protocols will interact with the Axis-Finance protocol. Creating auctions for big amounts, and promising big fees to some celebrities or influencers to promote their project. The funding parameter in the Routing struct is of type uint96
```solidity
struct Routing {
    ...
    uint96 funding;
    ...
}
```
The max amount of tokens with 18 decimals a uint96 variable can hold is around 80 billion. The problem arises in the curate() function, If the auction is prefunded, which all batch auctions are (a normal FPAM auction can also be prefunded), and the amount of prefunded tokens is big enough, close to 80 billion tokens with 18 decimals, and the curator fee is for example 7.5%, when the curatorFeePayout is added to the current funding, the funding will overflow.
```solidity
unchecked {
    routing.funding += curatorFeePayout;
}
```
Gist After following the steps in the above mentioned gist, add the following test to the AuditorTests.t.sol
```solidity
function test_CuratorFeeOverflow() public {
    vm.startPrank(alice);
    Keycode keycode = keycodeFromVeecode(veecode);
    bytes memory _derivativeParams = "";
    uint96 lotCapacity = 75_000_000_000e18; // this is 75 billion tokens
    mockBaseToken.mint(alice, 100_000_000_000e18);
    mockBaseToken.approve(address(auctionHouse), type(uint256).max);
    Auctioneer.RoutingParams memory routingA = Auctioneer.RoutingParams({
        auctionType: keycode,
        baseToken: mockBaseToken,
        quoteToken: mockQuoteToken,
        curator: curator,
        callbacks: ICallback(address(0)),
        callbackData: abi.encode(""),
        derivativeType: toKeycode(""),
        derivativeParams: _derivativeParams,
        wrapDerivative: false,
        prefunded: true
    });
    Auction.AuctionParams memory paramsA = Auction.AuctionParams({
        start: 0,
        duration: 1 days,
        capacityInQuote: false,
        capacity: lotCapacity,
        implParams: abi.encode(myStruct)
    });
    string memory infoHashA;
    auctionHouse.auction(routingA, paramsA, infoHashA);
    vm.stopPrank();
    vm.startPrank(owner);
    FeeManager.FeeType type_ = FeeManager.FeeType.MaxCurator;
    uint48 fee = 7_500; // 7.5% max curator fee
    auctionHouse.setFee(keycode, type_, fee);
    vm.stopPrank();
    vm.startPrank(curator);
    uint96 fundingBeforeCuratorFee;
    uint96 fundingAfterCuratorFee;
    (,fundingBeforeCuratorFee,,,,,,,) = auctionHouse.lotRouting(0);
    console2.log("Here is the funding normalized before curator fee is set: ", fundingBeforeCuratorFee/1e18);

    auctionHouse.setCuratorFee(keycode, fee);
    bytes memory callbackData_ = "";
    auctionHouse.curate(0, callbackData_);
    (,fundingAfterCuratorFee,,,,,,,) = auctionHouse.lotRouting(0);
    console2.log("Here is the funding normalized after curator fee is set: ", fundingAfterCuratorFee/1e18);

    console2.log("Balance of base token of the auction house: ", mockBaseToken.balanceOf(address(auctionHouse))/1e18);

    vm.stopPrank();
}
```
Logs:
Here is the funding normalized before curator fee is set: 75000000000
Here is the funding normalized after curator fee is set: 1396837485
Balance of base token of the auction house: 80625000000
To run the test use: forge test -vvv --mt test_CuratorFeeOverflow
If there is an overflow occurs in the curate() function, a big portion of the tokens will be stuck in the Axis-Finance protocol forever, as there is no way for them to be withdrawn, either by an admin function, or by canceling the auction (if an auction has started, only FPAM auctions can be canceled), as the amount returned is calculated in the following way
```solidity
if (routing.funding > 0) {
    uint96 funding = routing.funding;
    // Set to 0 before transfer to avoid re-entrancy
    routing.funding = 0;
    // Transfer the base tokens to the appropriate contract
    Transfer.transfer(
        routing.baseToken,
        _getAddressGivenCallbackBaseTokenFlag(routing.callbacks, routing.seller),
        funding,
        false
    );
    ...
}
```

## Proof of Concept

no poc

## Recommendation

Either remove the unchecked block
```solidity
routing.funding += curatorFeePayout;
```
so that when overflow occurs, the transaction will revert, or better yet also change the funding variable type from uint96 to uint256 this way sellers can create big enough auctions, and provide sufficient curator fee in order to bootstrap their protocol successfully.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unsigned integer overflow that occurs in the curate() function of the Axis‑Finance auction contract when the funding field, stored as a uint96, is increased by the curator fee payout without a safety check. The root cause is the choice of a 96‑bit unsigned integer to hold the amount of prefunded tokens, which can represent at most roughly 80 billion tokens with 18 decimals. When an auction is created with a prefunded amount close to this limit – for example 75 billion tokens – and a non‑zero curator fee such as 7.5 % is applied, the unchecked addition routing.funding += curatorFeePayout wraps around the uint96 range. The overflow reduces the stored funding value to a much smaller number while the contract’s internal balance still holds the original large amount. Exploitation is straightforward: an attacker (or even a legitimate seller) creates a large prefunded batch auction, sets a curator fee, and calls curate(). The overflow silently truncates the funding counter, and later when the contract attempts to return the remaining funds it reads the truncated value, transfers only that amount, and leaves the excess tokens locked in the contract forever because there is no admin or cancellation path that can recover the missing balance. The impact is a permanent loss of potentially billions of tokens, breaking the economic assumptions of the auction, depriving sellers and curators of expected payouts, and undermining confidence in the protocol. The condition for the bug to manifest is the combination of (1) a prefunded auction, (2) a funding amount that approaches the uint96 ceiling, and (3) a curator fee that triggers the unchecked addition. Users may notice that after setting the curator fee the reported funding drops dramatically (e.g., from 75 billion to 1.4 billion) while the contract’s token balance shows a much larger amount, leading to missing refunds or zero payouts where a substantial amount was expected. The issue was discovered during a manual audit by reproducing the scenario in a test that minted a large token supply and observed the overflow behavior. It is hard to spot because the overflow does not revert; it merely produces an unexpected low value that can be mistaken for a normal state, especially when logs are not closely inspected. The proper remediation is to eliminate the unchecked block so that any overflow triggers a revert, and preferably to replace the uint96 funding variable with a uint256 type, which can safely accommodate the full range of token supplies used by modern memecoins. This change restores correct accounting, ensures that curator fees are deducted safely, and prevents tokens from becoming irretrievably stuck in the contract.
