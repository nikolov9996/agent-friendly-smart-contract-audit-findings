---
id: 19624
severity: "High"
---

# wLp tokens could be stolen

## Description

`PosManager#removeCollateralWLpTo` function allows users to remove collateral wrapped in a wLp token that was previously supplied to the protocol:
```solidity
function removeCollateralWLpTo(uint _posId, address _wLp, uint _tokenId, uint _amt, address _receiver)
    external
    onlyCore
    returns (uint)
{
    PosCollInfo storage posCollInfo = __posCollInfos[_posId];
    // NOTE: balanceOfLp should be 1:1 with amt
    uint newWLpAmt = IBaseWrapLp(_wLp).balanceOfLp(_tokenId) - _amt;
    if (newWLpAmt == 0) { 
        _require(posCollInfo.ids[_wLp].remove(_tokenId), Errors.NOT_CONTAIN);
        posCollInfo.collCount -= 1;
        if (posCollInfo.ids[_wLp].length() == 0) {
            posCollInfo.wLps.remove(_wLp);
        }
        isCollateralized[_wLp][_tokenId] = false;
    }
    _harvest(_posId, _wLp, _tokenId);
    IBaseWrapLp(_wLp).unwrap(_tokenId, _amt, _receiver);
    return _amt;
}
```
This function could be called only from the core contract using the `decollateralizeWLp` and `liquidateWLp` functions. However, it fails to check if the specified `tokenId` belongs to the current position, this check would take place only if removing is full - meaning no lp tokens remain wrapped in the wLp (line 257).

This would allow anyone to drain any other positions with supplied wLp tokens. The attacker only needs to create its own position, supply dust amount in wLp to it, and call `decollateralizeWLp` with the desired ‘tokenId’, also withdrawn amount should be less than the full wLp balance to prevent check on line 257. An attacker would receive almost all lp tokens and accrued rewards from the victim’s wLp.

A similar attack for harvesting the victim’s rewards could be done through the `liquidateWLp` function.

## Proof of Concept

The next test added to the `tests/wrapper/TestWLp.sol` file could show an exploit scenario:
```solidity
function testExploitStealWlp() public {
    uint victimAmt = 100000000;
    // Bob open position with 'tokenId' 1
    uint bobPosId = _openPositionWithLp(BOB, victimAmt);
    // Alice open position with 'tokenId' 2 and dust amount 
    uint alicePosId = _openPositionWithLp(ALICE, 1);
    // Alice successfully de-collateralizes her own position using Bob's 'tokenId' and amounts less than Bob's position by 1 to prevent a revert
    vm.startPrank(ALICE, ALICE);
    initCore.decollateralizeWLp(alicePosId, address(mockWLpUniV2), 1, victimAmt - 1, ALICE);
    vm.stopPrank();

    emit log_uint(positionManager.getCollWLpAmt(bobPosId, address(mockWLpUniV2), 1));
    emit log_uint(IERC20(lp).balanceOf(ALICE));
}
```

## Recommendation

Consider adding a check that position holds the specified token into the `removeCollateralWLpTo` function:
```solidity
_require(__posCollInfos[_posId].ids[_wlp].contains(_tokenId), Errors.NOT_CONTAIN);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical access‑control flaw in the removeCollateralWLpTo function of the position manager contract. The function is intended to let a position owner withdraw wrapped LP (wLp) tokens that were supplied as collateral, but it does not verify that the supplied tokenId actually belongs to the position being operated on unless the withdrawal empties the entire wrapped balance (newWLpAmt == 0). Because the ownership check is only performed in the full‑withdrawal branch, an attacker can call the core contract’s decollateralizeWLp or liquidateWLp paths with a tokenId that belongs to a victim’s position while specifying an amount that leaves at least one wLp token behind. The contract then proceeds to harvest any accrued rewards and unwrap the requested amount to the attacker’s address, effectively draining the victim’s LP tokens and associated rewards. This can be triggered whenever a position holds wLp collateral and another user can create a separate position with a minimal dust amount of wLp, then invoke the removal function with the victim’s tokenId and an amount slightly smaller than the victim’s total balance. The impact is the loss of the victim’s underlying LP tokens and any earned rewards, which may appear to the user as a sudden disappearance of balance or a zero‑return on a withdrawal request. The issue was discovered during a formal audit by Code4rena when testing edge‑case interactions between decollateralizeWLp and the internal bookkeeping of token ownership. It is hard to notice because the transaction does not revert and the contract still reports a successful withdrawal, making the theft look like a normal operation from the UI perspective. Users see their wrapped LP balance reduced unexpectedly, often without any error message, leading to confusion and potential panic. The bug belongs to the class of missing authorization checks or improper state validation, where the contract assumes that the caller’s position implicitly owns the tokenId. The correct mitigation is to add an explicit verification that the position’s collateral mapping contains the tokenId before any amount is transferred, regardless of whether the withdrawal is full or partial. By enforcing this check, the contract would reject attempts to remove collateral that does not belong to the caller, preserving the integrity of the accounting and preventing unauthorized draining of LP assets.
