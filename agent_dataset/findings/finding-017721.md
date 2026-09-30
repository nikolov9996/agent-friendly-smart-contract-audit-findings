---
id: 17721
severity: "High"
---

# liquidationAccountant can be claimed at any

## Description

New liquidations are sent to the liquidationAccountant with a finalAuctionTimestamp value, but the actual value that is passed in is simply the duration of an auction. The claim() function uses this value in a require check, so this error will allow it to be called before the auction is complete. When a lien is liquidated, AstariaRouter.sol:liquidate() is called. If the lien is set to end in a future epoch, we call handleNewLiquidation() on the liquidationAccountant. One of the values passed in this call is the finalAuctionTimestamp, which updates the finalAuctionEnd variable in the liquidationAccountant. This value is then used to protect the claim() function from being called too early. However, when the router calls handleLiquidationAccountant(), it passes the
```solidity
LiquidationAccountant(accountant).handleNewLiquidation(
    lien.amount,
    COLLATERAL_TOKEN.auctionWindow() + 1 days
);
```
As a result, finalAuctionEnd will be set to 259200 (3 days). to be called:
```solidity
require(
    block.timestamp > finalAuctionEnd || finalAuctionEnd == uint256(0),
);
```
Because of the error above, block.timestamp will always be greater than finalAuctionEnd, so this will always be permitted. Anyone can call claim() before an auction has ended. This can cause many problems, but the clearest is that it can ruin the protocol's accounting by decreasing the Y intercept of the vault. For example, if claim() is called before the auction, the returned value will be 0, so the Y intercept will be decreased as if there was an auction that returned no funds.

## Proof of Concept

no poc

## Recommendation

Adjust the call from the router to use the ending timestamp as the argument, rather than the duration:
```solidity
LiquidationAccountant(accountant).handleNewLiquidation(
    lien.amount,
    block.timestamp + COLLATERAL_TOKEN.auctionWindow() + 1 days
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a time‑parameter misuse in the liquidation accounting flow. When a lien is liquidated, the router calls handleNewLiquidation on the LiquidationAccountant and passes COLLATERAL_TOKEN.auctionWindow() + 1 days, which represents the length of the auction rather than the absolute timestamp at which the auction should end. The accountant stores this value in finalAuctionEnd and the claim() function checks require(block.timestamp > finalAuctionEnd || finalAuctionEnd == 0). Because finalAuctionEnd contains only a small duration (for example 259200 seconds) instead of the future block time, the condition is true for any block.timestamp after deployment, allowing anyone to invoke claim() before the auction has actually completed. An attacker can therefore call claim() early, receive a zero payout, and cause the protocol’s accounting to record a loss of the expected auction revenue, effectively decreasing the Y‑intercept of the vault’s revenue curve. This mis‑recorded accounting can lead to incorrect distribution of rewards, under‑collateralization, or other financial inconsistencies. The issue appears only when the router uses the duration‑based call, which is the default path for all new liquidations, so it can be triggered by any participant. It was discovered during a manual audit that compared the intended semantics of finalAuctionEnd with the actual parameter passed. The bug is subtle because the require statement looks correct at a glance; the faulty value passes the check, and typical tests may not simulate an early claim. To remediate, the router must pass the absolute end timestamp (block.timestamp + auctionWindow + 1 day) so that finalAuctionEnd reflects the true auction deadline, causing the require check to reject premature claims. This class of bug falls under incorrect time calculation or logic error that breaks business‑logic invariants about auction finality and accounting integrity.
