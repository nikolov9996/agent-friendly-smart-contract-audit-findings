---
id: 21621
severity: "High"
---

# Attacker can perform a risk-free trade to mint free USDz tokens by opening then quickly closing positions for markets using negative `makerFee`

## Description

Attacker can perform a risk-free trade to mint free USDz tokens by opening then quickly closing positions in markets using negative `makerFee`; this is effectively a free mint exploit dressed up as a risk-free "trade".
The attacker can effectively perform a risk-free or minimal-risk trade to harvest free tokens via the negative `marginFee`; in the PoC the attacker was able to profit $796.
One potential invalidation for this attack vector is that in the real system the protocol controls the keepers who fill orders so an attacker couldn't force both trades into the same block in practice.
The real-world flow would go like this:
1) Attacker creates market order to buy (block 1)
2) Keeper fills buy order (block 2)
3) Attacker creates market order to sell (block 3)
4) Keeper fills sell order (block 4)
So it couldn't be done in one block in practice which means the attacker would be exposed to market movements for a tiny amount of time and that it isn't flash loan exploitable.
But it still seems quite exploitable to mint free tokens with very little exposure to market movements especially as the attacker is able to harvest the maker fee on both transactions by exploiting these 2 Low findings:
* `PerpMarket::getOrderFeeUsd rewards traders who flip the skew with makerFee for the full trade`
* `PerpMarket::getOrderFeeUsd incorrectly charges makerFee when skew is zero and trade is buy order`

## Proof of Concept

First change `script/markets/BtcUsd.sol` to have a negative `makerFee` like this:
```solidity
-    OrderFees.Data internal btcUsdOrderFees = OrderFees.Data({ makerFee: 0.0004e18, takerFee: 0.0008e18 });
+    OrderFees.Data internal btcUsdOrderFees = OrderFees.Data({ makerFee: -0.0004e18, takerFee: 0.0008e18 });
```
Then add PoC to `test/integration/perpetuals/order-branch/createMarketOrder/createMarketOrder.t.sol`:
```solidity
// new import at the top
import {console} from "forge-std/console.sol";

function test_AttackerMintsFreeUSDzOpenThenQuicklyClosePositionMarketNegMakerFee() external {
    // In a market with a negative maker fee, an attacker can perform
    // a risk-free "trade" by opening then quickly closing a position.
    // This allows attackers to mint free USDz without
    // any risk; it is essentially a free mint exploit dressed up
    // as a risk-free "trade"

    // give naruto some tokens
    uint256 USER_STARTING_BALANCE = 100_000e18;
    int128  USER_POS_SIZE_DELTA   = 10e18;
    deal({ token: address(usdToken), to: users.naruto, give: USER_STARTING_BALANCE });

    // naruto creates a trading account and deposits their tokens as collateral
    changePrank({ msgSender: users.naruto });
    uint128 tradingAccountId = createAccountAndDeposit(USER_STARTING_BALANCE, address(usdToken));

    // naruto opens position in BTC market
    openManualPosition(BTC_USD_MARKET_ID, BTC_USD_STREAM_ID, MOCK_BTC_USD_PRICE, tradingAccountId, USER_POS_SIZE_DELTA);

    // naruto closes position in BTC market immediately after
    // in practice this would occur one or more blocks after the
    // first order had been filled
    openManualPosition(BTC_USD_MARKET_ID, BTC_USD_STREAM_ID, MOCK_BTC_USD_PRICE, tradingAccountId, -USER_POS_SIZE_DELTA);

    // verify that now naruto has MORE USDz than they started with!
    uint256 traderCollateralBalance = perpsEngine.getAccountMarginCollateralBalance(tradingAccountId, address(usdToken)).intoUint256();
    assert(traderCollateralBalance > USER_STARTING_BALANCE);

    // naruto then withdraws all their collateral
    perpsEngine.withdrawMargin(tradingAccountId, address(usdToken), traderCollateralBalance);

    // verify that naruto has withdrawn more USDz than they deposited
    uint256 traderFinalUsdzBalance = usdToken.balanceOf(users.naruto);
    assert(traderFinalUsdzBalance > USER_STARTING_BALANCE);

    // output the profit
    console.log("Start USDz  : %s", USER_STARTING_BALANCE);
    console.log("Final USDz  : %s", traderFinalUsdzBalance);
    console.log("USDz profit : %s", traderFinalUsdzBalance - USER_STARTING_BALANCE);

    // profit = 796 040000000000000000
    //        = $796
}
```
Run with: `forge test --match-test test_AttackerMintsFreeUSDzOpenThenQuicklyClosePositionMarketNegMakerFee -vvv`

## Recommendation

Two possible options:
1) Don't allow negative `makerFee` / `takerFee`; change `leaves/OrderFees.sol` to use `uint128`.
2) If negative fees are desired implement a minimum time for which a position must remain open before it can be modified so that an attacker couldn't open a position then quickly close it to simply cash out the `makerFee`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a fee‑calculation flaw that allows an attacker to mint USDz tokens without taking market risk by exploiting a negative maker fee in a perpetual market. The contract’s getOrderFeeUsd function is designed to reward traders who flip the market skew, but it incorrectly permits a negative makerFee value and also applies the maker fee even when the market skew is zero and the order is a buy. Because the fee is stored as a signed integer, a negative makerFee creates a credit for the trader each time a position is opened or closed. An attacker can open a market order in a market that has been configured with a negative makerFee, receive a fee credit, and then immediately close the opposite position, receiving a second credit. The net effect is that the attacker’s collateral balance after the two trades is higher than the amount initially deposited, effectively minting free USDz. This can be performed with minimal exposure to price movements if the two trades are executed in rapid succession, ideally within the same block, although the real system’s keeper design may force the trades into separate blocks, still leaving a very short window of market risk. The issue impacts any user who can create a market order in a negatively‑fee‑configured market, the protocol’s token economics (inflating the supply of USDz), and ultimately the security of the whole platform. It was discovered during a security audit when the auditors modified the market configuration to set makerFee to a negative value and observed that the test account’s USDz balance increased after an open‑then‑close sequence. The problem is subtle because fee logic normally rewards activity, so a negative fee may appear as a harmless incentive, and the accounting checks do not flag a credit as an error. To remediate, the protocol should forbid negative maker or taker fees by using an unsigned integer type for fee parameters, and/or enforce a minimum holding period before a position can be closed so that a rapid open‑close loop cannot be used to harvest fee credits. In user‑facing terms, a trader expects to trade BTC for USDz and later receive the same amount back (minus fees), but instead sees their USDz balance grow unexpectedly, indicating a free‑mint scenario that violates the intended accounting model of the platform.
