---
id: 25375
severity: "Medium"
---

# GoodDollarExchangeProvider::mintFromExpansion() will change the price due to a rounding error in the new ratio

## Description



## Proof of Concept

Add the following test to `GoodDollarExchangeProvider.t.sol`:

```solidity
function test_POC_mintFromExpansion_priceChangeFix() public {
  uint256 priceBefore = exchangeProvider.currentPrice(exchangeId);
  vm.prank(expansionControllerAddress);
  exchangeProvider.mintFromExpansion(exchangeId, reserveRatioScalar);
  uint256 priceAfter = exchangeProvider.currentPrice(exchangeId);
  assertEq(priceBefore, priceAfter, "Price should remain exactly equal");
}
```

If the code is used as is, it fails. but if it is fixed by dividing and multiplying by `1e10`, eliminating the rounding error, the price matches exactly (exact fix show below).

## Recommendation

Divide and multiply `newRatio` by `1e10` to eliminate the rounding error, keeping the price unchanged.

```solidity
function mintFromExpansion(
  bytes32 exchangeId,
  uint256 reserveRatioScalar
) external onlyExpansionController whenNotPaused returns (uint256 amountToMint) {
  require(reserveRatioScalar > 0, "Reserve ratio scalar must be greater than 0");
  PoolExchange memory exchange = getPoolExchange(exchangeId);

  UD60x18 scaledRatio = wrap(uint256(exchange.reserveRatio) * 1e10);
  UD60x18 newRatio = wrap(unwrap(scaledRatio.mul(wrap(reserveRatioScalar))) / 1e10 * 1e10);
  ...
}
```
