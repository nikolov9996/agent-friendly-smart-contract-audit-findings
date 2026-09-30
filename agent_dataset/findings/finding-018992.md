---
id: 18992
severity: "High"
---

# The `_currentExchangeRate` of the Vault contract can’t increase and will always be lower than or equal to `_assetUnit`

## Description

The `_currentExchangeRate` of the Vault contract can not increase and will always be lower than or equal to `_assetUnit`. Therefore, when the vault is under-collateralized (`_currentExchangeRate` < `_assetUnit`), it can’t be further collateralized.

## Proof of Concept

```solidity
function _currentExchangeRate() internal view returns (uint256) {
    uint256 _totalSupplyAmount = _totalSupply();
    uint256 _totalSupplyToAssets = _convertToAssets(
      _totalSupplyAmount,
      _lastRecordedExchangeRate,
      Math.Rounding.Down
    );

    uint256 _withdrawableAssets = _yieldVault.maxWithdraw(address(this));

    if (_withdrawableAssets > _totalSupplyToAssets) {
      _withdrawableAssets = _withdrawableAssets - (_withdrawableAssets - _totalSupplyToAssets);
    }

    if (_totalSupplyAmount != 0 && _withdrawableAssets != 0) {
      return _withdrawableAssets.mulDiv(_assetUnit, _totalSupplyAmount, Math.Rounding.Down);
    }

    return _assetUnit;
  }
```
The `_totalSupplyAmount != 0 && _withdrawableAssets != 0`, `_currentExchangeRate` function will return a value `_withdrawableAssets * _assetUnit / _totalSupplyAmount`. However, `_withdrawableAssets` can not exceed `_totalSupplyToAssets`, which is equal to `_totalSupplyAmount * _lastRecordedExchangeRate / _assetUnit`. Therefore, `_currentExchangeRate` will always be lower than or equal to `_lastRecordedExchangeRate`.

Add this assert line and run `forge test`; all tests will pass.
```solidity
if (_totalSupplyAmount != 0 && _withdrawableAssets != 0) {
  assert(_withdrawableAssets.mulDiv(_assetUnit, _totalSupplyAmount, Math.Rounding.Down) <= _assetUnit);
  return _withdrawableAssets.mulDiv(_assetUnit, _totalSupplyAmount, Math.Rounding.Down);
}
```

## Recommendation

Remove the lines of code that limit the `_withdrawableAssets`:
```solidity
if (_withdrawableAssets > _totalSupplyToAssets) {
  _withdrawableAssets = _withdrawableAssets - (_withdrawableAssets - _totalSupplyToAssets);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical constraint in the Vault contract that prevents the internal exchange rate from ever increasing beyond the base asset unit. The function that computes the current exchange rate first determines the amount of assets that can be withdrawn from the underlying yield vault. It then forces this withdrawable amount to be no larger than the amount that corresponds to the total supply multiplied by the last recorded exchange rate. Because the withdrawable amount is capped, the subsequent calculation of exchange rate (withdrawableAssets * assetUnit / totalSupply) can never produce a value higher than the previously recorded rate. Consequently, when the vault becomes under‑collateralized – that is, when the computed exchange rate falls below the asset unit – the contract has no mechanism to raise the rate back up, effectively locking the vault in a state where additional collateral cannot be recognized. An attacker or a market event that pushes the vault into this state can therefore prevent future yield from being reflected in share values, causing users to receive fewer assets than expected on withdrawal, or to see their balances appear stagnant despite accrued interest. The issue was uncovered during a Code4rena audit when an assert was added that demonstrated the exchange rate never exceeds the asset unit, and all tests still passed, making the bug subtle. It is hard to notice because the function returns the asset unit when the supply or withdrawable amount is zero, and the cap does not produce an outright error. The bug violates the core accounting assumption that the exchange rate should be monotonic non‑decreasing as the vault earns yield. The recommended fix is to remove the code that artificially limits the withdrawable assets, allowing the exchange rate calculation to reflect the true growth of the underlying assets.
