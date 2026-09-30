---
id: 21219
severity: "High"
---

# Decreasing a position in PendleConnector will remove it even if there’s still a stake at Penpie

## Description

`decreasePosition()` will falsely remove the market as a holding position, ignoring the staked Pendle market LP tokens at Penpie and thus that stake won’t be counted towards the TVL of the connector and the TVL of the AccountingManager the connector belongs to.

## Proof of Concept

```solidity
function decreasePosition(IPMarket market, uint256 _amount, bool closePosition) external onlyManager nonReentrant {
    (IPStandardizedYield SY,,) = market.readTokens();
    (, address _underlyingToken,) = SY.assetInfo();

    // redeems an amount of base tokens by burning SY
    IERC20(address(SY)).safeTransfer(address(SY), _amount);
    IPStandardizedYield(address(SY)).redeem(address(this), _amount, _underlyingToken, 1, true);
    if (closePosition && isMarketEmpty(market)) {
        registry.updateHoldingPosition(
            vaultId,
            registry.calculatePositionId(address(this), PENDLE_POSITION_ID, abi.encode(market)),
            "",
            "",
            true
        );
    }
    emit DecreasePosition(address(market), _amount, closePosition);
}
```
When the `closePosition` parameter is true, `isMarketEmpty()` would be called for the given market to check if the connector holds any of the 3 tokens composing it - Yield token (YT), Principal token (PT) and Standardized Yield token (SY).
```solidity
function isMarketEmpty(IPMarket market) public view returns (bool) {
    (IPStandardizedYield _SY, IPPrincipalToken _PT, IPYieldToken _YT) = IPMarket(market).readTokens();
    return (
        _SY.balanceOf(address(this)) == 0 && _PT.balanceOf(address(this)) == 0 && _YT.balanceOf(address(this)) == 0
            && market.balanceOf(address(this)) == 0
    );
}
```
The function however does not check if the connector still has a balance in the Penpie pool for this market (a stake), and that will allow the connector to remove its holding position for a market, effectively excluding its stake in the Penpie pool from the connector and the AccountingManager TVL.

## Recommendation

In the `isMarketOpen()` function check for the connector’s balance in the Penpie staking pool for this market.
```solidity
diff --git a/contracts/connectors/PendleConnector.sol b/contracts/connectors/PendleConnector.sol
index 17607ee..e1b1208 100644
--- a/contracts/connectors/PendleConnector.sol
+++ b/contracts/connectors/PendleConnector.sol
@@ -304,7 +304,7 @@ contract PendleConnector is BaseConnector {
        (IPStandardizedYield _SY, IPPrincipalToken _PT, IPYieldToken _YT) = IPMarket(market).readTokens();
        return (
            _SY.balanceOf(address(this)) == 0 && _PT.balanceOf(address(this)) == 0 && _YT.balanceOf(address(this)) == 0
-               && market.balanceOf(address(this)) == 0
+               && market.balanceOf(address(this)) == 0 && pendleMarketDepositHelper.balance(market, address(this)) == 0
        );
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the PendleConnector contract that manages Pendle market positions. When a caller invokes decreasePosition with the closePosition flag set to true, the function checks whether the market is empty by calling isMarketEmpty. The isMarketEmpty routine examines the balances of the three core tokens of the market – the standardized yield token, the principal token and the yield token – as well as the market token balance held directly by the connector. However, it completely ignores any balance that the connector may have deposited in the external Penpie staking pool for that market. As a result, if the connector still holds a stake in Penpie, the isMarketEmpty function incorrectly returns true, causing the connector to call registry.updateHoldingPosition with the flag that removes the holding position from the AccountingManager. This logical omission leads to the market being removed from the connector’s list of active holdings even though a stake remains in Penpie. From a user perspective the UI will show that the market has disappeared from the portfolio and the reported total value locked (TVL) for the connector drops, while the underlying LP tokens are still locked in the Penpie pool and cannot be accounted for or withdrawn correctly. The impact is a mismatch in accounting, under‑reporting of TVL, loss of visibility of staked assets and potential inability to claim rewards that depend on the recorded holdings. The bug manifests only when closePosition is true and there is a non‑zero balance in the Penpie pool; otherwise the original logic works as intended. It affects any protocol component that relies on the AccountingManager’s TVL, including investors, auditors and downstream applications that display portfolio data. The issue was discovered during a Code4rena audit by inspecting the logic of decreasePosition and noticing that the external staking balance was not considered. It can be hard to notice because the connector’s direct token balances are zero, which is the usual indicator of an empty market, while the hidden stake resides in a separate contract that is not obvious from a simple balance check. The class of bug is an incomplete state validation or logical omission where external asset holdings are not included in emptiness checks. To remediate, the isMarketEmpty (or the related isMarketOpen) function should be extended to also query the Penpie staking helper for the connector’s balance in that pool and require it to be zero before treating the market as empty. This ensures that a market is only removed when all associated assets, including those locked in external staking contracts, have been fully withdrawn, preserving accurate TVL reporting and preventing accidental removal of active positions.
