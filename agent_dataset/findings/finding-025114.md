---
id: 25114
severity: "Crit/High"
---

# Admin new issuance or user calling Vault::redeemExpiredLv() after Psm::redeemWithCt() will lead to stuck funds when trying to withdraw

## Description



## Proof of Concept

`ModuleCore::issueNewDs()` calls `PsmLib::onNewIssuance()` before `VaultLib::onNewIssuance()` always triggering this bug.

```solidity
function issueNewDs(Id id, uint256 expiry, uint256 exchangeRates, uint256 repurchaseFeePrecentage)
    external
    override
    onlyConfig
    onlyInitialized(id)
{
    ...
    PsmLibrary.onNewIssuance(state, ct, ds, ammPair, idx, prevIdx, repurchaseFeePrecentage);

    getRouterCore().onNewIssuance(id, idx, ds, ammPair, 0, ra, ct);

    VaultLibrary.onNewIssuance(state, prevIdx, getRouterCore(), getAmmRouter());
    ...
}
```

`PsmLib::_separateLiquidity()` checkpoints `ra` and `pa` based on `ct` supply:

```solidity
function _separateLiquidity(State storage self, uint256 prevIdx) internal {
    ...
    self.psm.poolArchive[prevIdx] = PsmPoolArchive(availableRa, availablePa, IERC20(ds.ct).totalSupply());
    ...
}
```

`VaultLib::_liquidatedLp()` redeems `ra` with `ct` and `ds` when it should have skipped it has liquidity has already been checkpointed in `PsmLib::_separateLiquidity()`.

```solidity
function _liquidatedLp(
    State storage self,
    uint256 dsId,
    IUniswapV2Router02 ammRouter,
    IDsFlashSwapCore flashSwapRouter
) internal {
    ...
    PsmLibrary.lvRedeemRaWithCtDs(self, redeemAmount, dsId);

    // if the reserved DS is more than the CT that's available from liquidating the AMM LP
    // then there's no CT we can use to effectively redeem RA + PA from the PSM
    uint256 ctAttributedToPa = reservedDs >= ctAmm ? 0 : ctAmm - reservedDs;

    uint256 psmPa;
    uint256 psmRa;

    if (ctAttributedToPa != 0) {
        (psmPa, psmRa) = PsmLibrary.lvRedeemRaPaWithCt(self, ctAttributedToPa, dsId);
    }

    psmRa += redeemAmount;

    self.vault.pool.reserve(self.vault.lv.totalIssued(), raAmm + psmRa, psmPa);
}
```

## Impact

As the `Vault` withdraws `Ra` after the checkpoint and burns the corresponding `Ct` tokens, it will withdraw too many `ra` and not withdraw the `pa` it was entitled to.

## Recommendation

If the liquidity has been separated, skip redeeming `ra` for `ct` and `ds`.

```solidity
function _liquidatedLp(
    State storage self,
    uint256 dsId,
    IUniswapV2Router02 ammRouter,
    IDsFlashSwapCore flashSwapRouter
) internal {
    ...
    if (!self.psm.liquiditySeparated.get(prevIdx)) {
        PsmLibrary.lvRedeemRaWithCtDs(self, redeemAmount, dsId);
    }
    ...
}
```
