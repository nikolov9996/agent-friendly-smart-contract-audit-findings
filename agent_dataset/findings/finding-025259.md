---
id: 25259
severity: "Medium"
---

# repay(), liquidate() and liquidateWLp() receive shares as argument, which may revert if from approval to tx settled blocks have passed

## Description



## Proof of Concept

A test when repaying debt was carried out in `TestInitCore.sol`. The timestamp increased just 1 second, but it was enough to make the transaction revert. It may be possible to request a bigger alowance than expected, but this has other implications.

```
function test_POC_TransferFromFails_DueToDebtAccrual() public {
    uint256 _wbtcAmount = 3e8;
    uint256 _borrowAmount = 1e8;
    address _user = makeAddr("user");
    deal(WBTC, _user, _wbtcAmount);

    uint256 _posId = _createPos(_user, _user, 2);
    uint256 shares_ = _mintPool(_user, address(lendingPools[WBTC]), _wbtcAmount, "");
    vm.startPrank(_user);
    lendingPools[WBTC].transfer(address(positionManager), shares_);
    initCore.collateralize(_posId, address(lendingPools[WBTC]));
    vm.stopPrank();

    uint256 _debtShares = _borrow(_user, _posId, address(lendingPools[WBTC]), _borrowAmount, "");

    uint256 _userDebtBalance = lendingPools[WBTC].debtShareToAmtCurrent(_debtShares);

    vm.prank(_user);
    IERC20(WBTC).approve(address(initCore), _userDebtBalance);

    skip(1);

    vm.prank(_user);
    vm.expectRevert("ERC20: transfer amount exceeds balance");
    initCore.repay(address(lendingPools[WBTC]), _debtShares, _posId);
}
```

## Recommendation

Receive the amount in InitCore as argument instead of the shares on the `repay()`, `liquidate()` and `liquidateWLp()` functions.
