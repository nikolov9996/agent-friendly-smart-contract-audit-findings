---
id: 25377
severity: "Medium"
---

# User to sell the last supply will make the exchange contribution forever stuck

## Description



## Proof of Concept

Add the following test to `BancorExchangeProvider.t.sol`:

```solidity
function test_POC_swapIn_whenTokenInIsToken_shouldSwapIn() public {
  BancorExchangeProvider bancorExchangeProvider = initializeBancorExchangeProvider();
  uint256 amountIn =  300_000 * 1e18;

  bytes32 exchangeId = bancorExchangeProvider.createExchange(poolExchange1);

  vm.startPrank(brokerAddress);
  uint256 amountOut = bancorExchangeProvider.swapIn(exchangeId, address(token), address(reserveToken), amountIn);

  (, , uint256 tokenSupplyAfter, uint256 reserveBalanceAfter, , ) = bancorExchangeProvider.exchanges(exchangeId);

  assertEq(amountOut, 59400e18);
  assertEq(reserveBalanceAfter, 600e18);
  assertEq(tokenSupplyAfter, 0);

  vm.expectRevert("ERR_INVALID_SUPPLY");
  bancorExchangeProvider.swapIn(exchangeId, address(token), address(reserveToken), 1e18);
}
```

## Recommendation

The specific mitigation depends on the design.
