---
id: 9034
severity: "High"
---

# Trapped underlying tokens in the auction

## Description

During an insolvency event, the governance can take underlying tokens
from the StakedToken contract and auction them using the function
SafetyModule::slashAndStartAuction . This action sends the underlying
tokens to the AuctionModule.sol contract, initiating the auction.
Subsequently, the auction can be closed using the
AuctionModule::_completeAuction function. This function can be called when
all underlying tokens are auctioned in AuctionModule::buyLots , when the
auction expires and someone decides to end the auction with the function
AuctionModule::completeAuction , or when governance decides to terminate
the auction early with the function SafetyModule::terminateAuction .
The issue arises when there are no restrictions on redeeming staked tokens
during the auction process. Users can completely exit and redeem all their
tokens. Later, when attempting to close the auction, it will fail due to a
division by zero error . This happens because when
AuctionModule::_completeAuction is called, it invokes
StakedToken::returnFunds and then updates the exchange rate using the
function StakedToken::_updateExchangeRate . This function performs a
division by totalSupply() , which is zero (code line StakedToken#L240 ):
```solidity
File: StakedToken.sol
235: function returnFunds
(address from, uint256 amount) external onlySafetyModule {
236: if (amount == 0) revert StakedToken_InvalidZeroAmount();
237: if (from == address(0)) revert StakedToken_InvalidZeroAddress();
239: // Update the exchange rate
240: _updateExchangeRate(UNDERLYING_TOKEN.balanceOf(address
(this)) + amount, totalSupply());
242: // Transfer the underlying tokens back to this contract
243: UNDERLYING_TOKEN.safeTransferFrom(from, address(this), amount);
244: emit FundsReturned(from, amount);
245: }
```
Consider the following scenario:
1. UserA stakes 100e18 underlyingTokens and receives 100e18 staked
tokens .
2. An insolvency event occurs, and a 20e18 underlyingTokens auction is
initiated.
3. UserA decides to redeem all their tokens, leaving
stakedToken.totalSupply=0 .
4. The auction ends, and AuctionModule::_completeAuction is called, but it
cannot close due to a division by zero error .
5. The last lot cannot be bought, as the function AuctionModule::buyLots
attempts to close the auction, resulting in a transaction being reverted due to
a division by zero error .
6. The staked token becomes unusable since staking is no longer possible
( isInPostSlashingState is true).
7. The underlying tokens that were not auctioned remain trapped within
AuctionModule .
I conducted the following test, which demonstrates that ending an auction will
be reversed when liquidityProviderOne redeems all the staked tokens ,
leaving the remaining underlying tokens trapped in AuctionModule.sol :
```solidity
// Filename: test/unit/SafetyModuleTest.sol:SafetyModuleTest
// $ forge test --match-test "testFuzz_TerminateAuctionErrorZero" -vvv
function testFuzz_TerminateAuctionErrorZero(
    uint8 numLots,
    uint128 lotPrice,
    uint128 initialLotSize,
    uint64 slashPercent,
    uint16 lotIncreasePeriod,
    uint32 timeLimit
) public {
    /* bounds */
    numLots = uint8(bound(numLots, 2, 10));
    lotPrice = uint128(bound
    //(lotPrice, 1e8, 1e12)); // denominated in USDC w/ 6 decimals
    slashPercent = uint64(bound(slashPercent, 1e16, 1e18));
    // lotSize x numLots should not exceed auctionable balance
    uint256 auctionableBalance = stakedToken1.totalSupply().wadMul
    (slashPercent);
    initialLotSize = uint128(bound
    (initialLotSize, 1e18, auctionableBalance / numLots));
    uint96 lotIncreaseIncrement = uint96(bound
    (initialLotSize / 50, 2e16, type(uint96).max));
    lotIncreasePeriod = uint16(bound(lotIncreasePeriod, 1 hours, 18 hours));
    timeLimit = uint32(bound(timeLimit, 5 days, 30 days));
    // 1. Start an auction and check that it was created correctly
    uint256 auctionId = _startAndCheckAuction(
        stakedToken1,
        numLots,
        lotPrice,
        initialLotSize,
        slashPercent,
        lotIncreaseIncrement,
        lotIncreasePeriod,
        timeLimit
    // 2. `liquidityProviderOne` redeems all tokens
    vm.startPrank(liquidityProviderOne);
    uint256 stakedBalance = stakedToken1.balanceOf(liquidityProviderOne);
    stakedToken1.redeem(stakedBalance);
    vm.stopPrank();
    // 3. `SafetyModule` terminates auction, the transaction will be
    // reverted by "panic: division or modulo by zero"
    vm.expectRevert();
    safetyModule.terminateAuction(auctionId);
    // 4. underlying token trapped in `AuctionModule` contract
    assertGt(stakedToken1.getUnderlyingToken().balanceOf(address
    //(auctionModule)), 0); // AuctionModule.underlyingBalance > 0
```

## Proof of Concept

No poc.

## Recommendation

```solidity
It is suggested that when stakedToken.totalSupply=0 , the exchangeRate
should be set to 1e18 .
function _updateExchangeRate
(uint256 totalAssets, uint256 totalShares) internal {
++ if (totalShares == 0)
++ exchangeRate = 1e18;
++ else
++ exchangeRate = totalAssets.wadDiv(totalShares);
    emit ExchangeRateUpdated(exchangeRate);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic error that occurs when the exchange rate of a staked token is updated after an auction has been started and all staked tokens are redeemed. The root cause is that the function responsible for updating the exchange rate divides the total underlying assets by the total supply of staked tokens without first checking whether the total supply is zero. During a normal insolvency event the governance contract can move underlying tokens to an auction module and later close the auction. If a user redeems all of their staked tokens while the auction is still open, the total supply becomes zero. When the auction is later closed, the auction module calls the token contract to return any remaining funds and then invokes the exchange‑rate update. Because the total supply is zero, the division triggers a division‑by‑zero panic and the transaction reverts. This prevents the auction from completing, leaves the last lot unsold and traps the remaining underlying tokens inside the auction contract. From a user’s point of view the expected flow – stake, possibly be slashed, then receive a refund or retrieve the underlying asset – is broken: a user can successfully redeem their balance, but later the protocol cannot finish the auction and the funds that should have been sold or returned stay locked in an inaccessible contract. The impact is that a portion of the protocol’s collateral becomes permanently unavailable, staking becomes impossible because the contract stays in a post‑slashing state, and the protocol’s accounting assumptions about total supply and exchange rate are violated. The condition under which this occurs is specific to an insolvency event where an auction is started and the contract allows unrestricted redemption of staked tokens during the auction. It affects token holders who try to exit, the governance that cannot close the auction, and the overall protocol security because locked funds reduce the available collateral. The issue was discovered during a security audit by reproducing a scenario in which a liquidity provider redeemed all tokens and the subsequent call to terminate the auction reverted with a panic message indicating division or modulo by zero. The bug is hard to notice because the division‑by‑zero only happens after the total supply reaches zero, a state that is not normally reached in regular operation, and the revert message does not directly point to the underlying accounting flaw. The recommended fix is to guard the division by checking if totalShares (total supply) is zero and, in that case, set the exchange rate to a neutral value such as 1e18 instead of performing the division. Alternatively, the protocol could prohibit redemption while an auction is active, ensuring that total supply never drops to zero before the auction is settled. Either approach restores the ability to close the auction, prevents underlying tokens from being trapped, and re‑establishes correct accounting of exchange rates.
