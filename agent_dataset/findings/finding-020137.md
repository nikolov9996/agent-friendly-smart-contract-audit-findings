---
id: 20137
severity: "High"
---

# setSymbolsPrice() can use the priceSig from multiple times

## Description

```solidity
setSymbolsPrice() only restricts the maximum value of priceSig.timestamp, but not the minimum time. This allows a malicious user to choose a malicious priceSig from a long time ago. A malicious priceSig.upnl can seriously harm partyB.
setSymbolsPrice() only restricts the maximum value of priceSig.timestamp, but not the minimum time
function setSymbolsPrice(address partyA, PriceSig memory priceSig) internal {
    MAStorage.Layout storage maLayout = MAStorage.layout();
    AccountStorage.Layout storage accountLayout = AccountStorage.layout();
    LibMuon.verifyPrices(priceSig, partyA);
    require(
        priceSig.timestamp <=
        maLayout.liquidationTimestamp[partyA] +
        maLayout.liquidationTimeout,
        "LiquidationFacet: Expired signature"
    );
```
LibMuon.verifyPrices only check sign, without check the time range
```solidity
function verifyPrices(PriceSig memory priceSig, address partyA) internal view {
    MuonStorage.Layout storage muonLayout = MuonStorage.layout();
    require(priceSig.prices.length == priceSig.symbolIds.length, "LibMuon: Invalid length");
    bytes32 hash = keccak256(
        abi.encodePacked(
            muonLayout.muonAppId,
            priceSig.reqId,
            address(this),
            partyA,
            priceSig.upnl,
            priceSig.totalUnrealizedLoss,
            priceSig.symbolIds,
            priceSig.prices,
            priceSig.timestamp,
            getChainId()
        )
    );
    verifyTSSAndGateway(hash, priceSig.sigs, priceSig.gatewaySignature);
}
```
In this case, a malicious user may pick any priceSig from a long time ago, and this priceSig may have a large negative upnl, leading to LiquidationType.OVERDUE, severely damaging partyB.
We need to restrict priceSig.timestamp to be no smaller than maLayout.liquidationTimestamp[partyA] to avoid this problem.
Maliciously choosing the illegal PriceSig thus may hurt others user

## Proof of Concept

no poc

## Recommendation

restrict priceSig.timestamp to be no smaller than maLayout.liquidationTimestamp[partyA]
```solidity
function setSymbolsPrice(address partyA, PriceSig memory priceSig) internal {
    MAStorage.Layout storage maLayout = MAStorage.layout();
    AccountStorage.Layout storage accountLayout = AccountStorage.layout();
    LibMuon.verifyPrices(priceSig, partyA);
    require(maLayout.liquidationStatus[partyA], "LiquidationFacet: PartyA is solvent");
    require(
        priceSig.timestamp <=
        maLayout.liquidationTimestamp[partyA] +
        maLayout.liquidationTimeout,
        "LiquidationFacet: Expired signature"
    );
    require(priceSig.timestamp >=
    maLayout.liquidationTimestamp[partyA],"invald price timestamp");
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the function that records a price signature (setSymbolsPrice) used for liquidation calculations. The code only checks that the timestamp of the supplied price signature is not later than the allowed liquidation deadline, but it does not enforce a lower bound on the timestamp. As a result, an attacker can replay a previously signed priceSig that was created at any earlier point in time. The verification routine (LibMuon.verifyPrices) validates the cryptographic signature and the internal consistency of the arrays, yet it never validates that the timestamp falls within a recent, expected window. Consequently, a malicious actor can submit a stale priceSig whose upnl field contains a large negative value, causing the liquidation logic to interpret the position as overdue and trigger a LiquidationType.OVERDUE. This forces the protocol to liquidate the counter‑party (partyB) under false pretenses, potentially draining their collateral or reducing their balance to zero. The impact is severe: users of the protocol may lose funds unexpectedly, the accounting model that assumes price data reflects the current market is broken, and the trust in the liquidation mechanism is undermined. The issue manifests whenever setSymbolsPrice is called with a priceSig whose timestamp is older than the current liquidation timestamp for the party; there is no safeguard preventing such replay. It affects any participant that relies on the liquidation process, especially the counter‑party whose position is liquidated (partyB). The flaw was discovered during a manual audit that examined the timestamp checks and noticed the missing lower‑bound condition. Because the signature itself is valid, the bug can be subtle and may not raise obvious errors; the contract behaves as designed, yet the business logic is violated, making the problem hard to spot without a focused review of time‑range validation. The appropriate remediation is to enforce that priceSig.timestamp is greater than or equal to the stored liquidationTimestamp for the party, thereby preventing the use of stale signatures. This class of bug is a replay‑or‑stale‑data vulnerability where time‑based constraints are incomplete, leading to incorrect financial calculations and unintended liquidations.
