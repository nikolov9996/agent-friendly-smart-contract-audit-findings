---
id: 2621
severity: "High"
---

# Admin new issuance or user calling Vault::redeemExpiredLv() after Psm::redeemWithCt() will lead to stuck funds when trying to withdraw Found by 0x73696d616f

## Description

VaultLib::_liquidatedLp() calls PsmLib::lvRedeemRaWithCtDs(), which redeems ra with ct and ds. However, if PsmLib::_separateLiquidity() has already been called, this will lead to an incorrect tracking of funds as PsmLib::_separateLiquidity() checkpointed the total supply of ct, but the Vault will redeem some of it using PsmLib::lvRedeemRaWithCtDs(), leading to some pa that will never be withdrawn and the vault withdraws too many Ra, which means users will not be able to redeem their ct for ra and pa as ra has been withdrawn already and it reverts.  
In VaultLib.sol:377, it calls PsmLib::lvRedeemRaWithCtDs() even if PsmLib::_separateLiquidity() has already been called. It should skip it in this case.  

Internal pre-conditions  
1. PsmLib::_separateLiquidity() needs to be called before VaultLib::_liquidatedLp(), which may be done on a new issuance when the admin calls ModuleCore::issueNewDs() or by users calling Psm::redeemWithCT() before Vault::redeemExpiredLv().  

External pre-conditions  
None.  

Attack Path  
1. Admin calls ModuleCore::issueNewDs(). Or users call Psm::redeemWithCT() before Vault::redeemExpiredLv().  
As the Vault withdraws Ra after the checkpoint and burns the corresponding Ct tokens, it will withdraw too many ra and not withdraw the pa it was entitled to.

## Proof of Concept

ModuleCore::issueNewDs() calls PsmLib::onNewIssuance() before VaultLib::onNewIssuance() always triggering this bug.  
```solidity
function issueNewDs(Id id, uint256 expiry, uint256 exchangeRates, uint256 repurchaseFeePrecentage) external override onlyConfig onlyInitialized(id) {
    ...
    PsmLibrary.onNewIssuance(state, ct, ds, ammPair, idx, prevIdx, repurchaseFeePrecentage);
    getRouterCore().onNewIssuance(id, idx, ds, ammPair, 0, ra, ct);
    VaultLibrary.onNewIssuance(state, prevIdx, getRouterCore(), getAmmRouter());
    ...
}
```

PsmLib::_separateLiquidity() checkpoints ra and pa based on ct supply:  
```solidity
function _separateLiquidity(State storage self, uint256 prevIdx) internal {
    ...
    self.psm.poolArchive[prevIdx] = PsmPoolArchive(availableRa, availablePa, IERC20(ds.ct).totalSupply());
    ...
}
```

VaultLib::_liquidatedLp() redeems ra with ct and ds when it should have skipped it has liquidity has already been checkpointed in PsmLib::_separateLiquidity().  
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

## Recommendation

If the liquidity has been separated, skip redeeming ra for ct and ds.  
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

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch that occurs when the vault attempts to redeem RA (the protocol’s primary asset) for CT (the collateral token) after the PSM (Pegged Stablecoin Module) has already performed a liquidity separation. The PSM library function _separateLiquidity records a checkpoint of the total CT supply and the amounts of RA and PA (the protocol’s secondary asset) that are available at that moment. Later, VaultLib::_liquidatedLp calls PsmLibrary.lvRedeemRaWithCtDs to redeem RA using CT and DS (a debt token) without checking whether the liquidity has already been separated. Because the checkpointed CT total no longer matches the actual CT balance after the earlier separation, the vault ends up withdrawing more RA than it should and fails to withdraw the PA that it is entitled to. This mismatch leaves a portion of PA permanently locked in the vault and causes the subsequent redeem operation to revert, meaning users cannot exchange their CT for the expected RA and PA. The bug can be triggered in two ways: an admin can call ModuleCore::issueNewDs, which internally invokes PsmLibrary.onNewIssuance before VaultLibrary.onNewIssuance, or a regular user can call Psm::redeemWithCT before Vault::redeemExpiredLv. In both cases the pre‑condition that _separateLiquidity has already been executed is satisfied, but the vault does not skip the redundant redemption step. The impact is high: funds become stuck, users see their balances unchanged or receive a transaction revert, and the protocol’s accounting guarantees are broken. The issue was discovered during a manual audit that traced the flow of state between the PSM and the vault and noticed that the liquiditySeparated flag was never consulted before the redemption call. It is subtle because the code paths appear independent and the error only manifests after a specific sequence of calls, making it easy to miss in routine testing. The correct mitigation is to add a guard that checks the liquiditySeparated flag and skips the lvRedeemRaWithCtDs call when liquidity has already been separated, thereby preserving the integrity of the RA/PA accounting and preventing funds from becoming unrecoverable.
