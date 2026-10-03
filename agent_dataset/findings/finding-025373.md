---
id: 25373
severity: "Medium"
---

# Malicious user may frontrun GoodDollarExpansionController::mintUBIFromReserveBalance() to make protocol funds stuck

## Description



## Proof of Concept

`GoodDollarExpansionController::mintUBIFromInterest()` and `GoodDollarExpansionController::mintUBIFromReserveBalance()` do not check if `amountToMint` is null:

```solidity
function mintUBIFromInterest(bytes32 exchangeId, uint256 reserveInterest) external {
  require(reserveInterest > 0, "Reserve interest must be greater than 0");
  IBancorExchangeProvider.PoolExchange memory exchange = IBancorExchangeProvider(address(goodDollarExchangeProvider))
    .getPoolExchange(exchangeId);

  uint256 amountToMint = goodDollarExchangeProvider.mintFromInterest(exchangeId, reserveInterest);

  require(IERC20(exchange.reserveAsset).transferFrom(msg.sender, reserve, reserveInterest), "Transfer failed"); //@audit safeTransferFrom.  //@audit lost if reserve asset is also a stable asset
  IGoodDollar(exchange.tokenAddress).mint(address(distributionHelper), amountToMint);

  // Ignored, because contracts only interacts with trusted contracts and tokens
  // slither-disable-next-line reentrancy-events
  emit InterestUBIMinted(exchangeId, amountToMint);
}

...

function mintUBIFromReserveBalance(bytes32 exchangeId) external returns (uint256 amountMinted) {
  IBancorExchangeProvider.PoolExchange memory exchange = IBancorExchangeProvider(address(goodDollarExchangeProvider))
    .getPoolExchange(exchangeId);

  uint256 contractReserveBalance = IERC20(exchange.reserveAsset).balanceOf(reserve);
  uint256 additionalReserveBalance = contractReserveBalance - exchange.reserveBalance;
  if (additionalReserveBalance > 0) {
    amountMinted = goodDollarExchangeProvider.mintFromInterest(exchangeId, additionalReserveBalance);
    IGoodDollar(exchange.tokenAddress).mint(address(distributionHelper), amountMinted);

    // Ignored, because contracts only interacts with trusted contracts and tokens
    // slither-disable-next-line reentrancy-events
    emit InterestUBIMinted(exchangeId, amountMinted);
  }
}
```

`GoodDollarExchangeProvider::mintFromInterest()` returns 0 if `exchange.tokenSupply` is 0.

```solidity
function mintFromInterest(
  bytes32 exchangeId,
  uint256 reserveInterest
) external onlyExpansionController whenNotPaused returns (uint256 amountToMint) {
  PoolExchange memory exchange = getPoolExchange(exchangeId);

  uint256 reserveinterestScaled = reserveInterest * tokenPrecisionMultipliers[exchange.reserveAsset];
  uint256 amountToMintScaled = unwrap(
    wrap(reserveinterestScaled).mul(wrap(exchange.tokenSupply)).div(wrap(exchange.reserveBalance))
  );
  amountToMint = amountToMintScaled / tokenPrecisionMultipliers[exchange.tokenAddress];

  exchanges[exchangeId].tokenSupply += amountToMintScaled;
  exchanges[exchangeId].reserveBalance += reserveinterestScaled;

  return amountToMint;
}
```

## Recommendation

Revert if the `amountToMint` from the `GoodDollarExchangeProvider::mintFromInterest()` call is null. The same should also be done for `GoodDollarExpansionController::mintUBIFromExpansion()` `amountMinted` from the `GoodDollarExchangeProvider.mintFromExpansion()` call.
