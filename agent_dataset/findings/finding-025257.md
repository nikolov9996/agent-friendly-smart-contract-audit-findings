---
id: 25257
severity: "Medium"
---

# Decimals of LendingPool don't take into account the offset introduced by VIRTUAL_SHARES

## Description



## Proof of Concept

The Openzeppelin [implementation](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol#L106-L108>) includes the decimals offset (log10(`VIRTUAL_SHARES`) in LendingPool) in the `decimals()` function. However, INIT only places the decimals of the [underlying](<https://github.com/code-423n4/2023-12-initcapital/blob/main/contracts/lending_pool/LendingPool.sol#L95-L97>).

A POC was built, add it to `TestLendingPool.sol`:

```
function test_POC_WrongDecimals() public {
    uint256 _wbtcAmount = 3e8; // 3 BTC
    address _user = makeAddr("user");
    _mintPool(_user, WBTC, _wbtcAmount);
    uint256 _wbtcDecimals = 1e8;
    uint256 VIRTUAL_SHARES = 1e8;
    uint256 _poolDecimals = 10**lendingPools[WBTC].decimals();
    uint256 _userBalance = lendingPools[WBTC].balanceOf(_user);
    assertEq(_userBalance/_poolDecimals, _wbtcAmount/_wbtcDecimals*VIRTUAL_SHARES);
    assertEq(_userBalance/_poolDecimals, 3e8);
    assertEq(_userBalance, _wbtcAmount*VIRTUAL_SHARES);
}
```

## Recommendation

Include the virtual shares decimals in the `decimals()` function:

```
uint private constant VIRTUAL_SHARES = 8;
...
function decimals() public view override returns (uint8) {
    return IERC20Metadata(underlyingToken).decimals() + VIRTUAL_SHARES;
}
...
function _toShares(uint _amt, uint _totalAssets, uint _totalShares) internal pure returns (uint shares) {
    return _amt.mulDiv(_totalShares + 10**VIRTUAL_SHARES, _totalAssets + VIRTUAL_ASSETS);
}
...
function _toAmt(uint _shares, uint _totalAssets, uint _totalShares) internal pure returns (uint amt) {
    return _shares.mulDiv(_totalAssets + VIRTUAL_ASSETS, _totalShares + 10**VIRTUAL_SHARES);
}
```
