---
id: 25147
severity: "Medium"
---

# Utilization rates are 0 when average assets are 0, which may be used to game maturity borrows / deposits / withdrawals

## Description



## Proof of Concept

## Vulnerability Detail

In `Market::initialize()`, `lastAverageUpdate` is set to `block.timestamp`. When calculating the average assets, the formula used is:

```solidity
function previewFloatingAssetsAverage() public view returns (uint256) {
  uint256 memFloatingAssets = floatingAssets;
  uint256 memFloatingAssetsAverage = floatingAssetsAverage;
  uint256 dampSpeedFactor = memFloatingAssets < memFloatingAssetsAverage ? dampSpeedDown : dampSpeedUp;
  uint256 averageFactor = uint256(1e18 - (-int256(dampSpeedFactor * (block.timestamp - lastAverageUpdate))).expWad());
  return memFloatingAssetsAverage.mulWadDown(1e18 - averageFactor) + averageFactor.mulWadDown(memFloatingAssets);
}
```

As can be seen, if `block.timestamp == lastAverageUpdate`, `averageFactor` will be `1 - e^0 = 0`, resulting in average assets equal to `memFloatingAssetsAverage`, which is `0` when no deposits were made. Thus, even if a user deposits and borrows, its deposit will still lead to `previewFloatingAssetsAverage() == 0`, allowing him to get a borrow, even if almost as big as its deposit (minus the adjust factor), using the lowest interest rate possible.

The following test confirms this behaviour, add it to `Market.t.sol`:

```solidity
function test_POC_BorrowAtMaturity_LowestRate() external {
  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, assets + 1);
  uint256 maturity = FixedLib.INTERVAL * 2;

  //skip(1 days); // Uncomment to confirm that if some time passes assetsOwed will increase

  vm.startPrank(ALICE);
  market.deposit(assets, ALICE);
  uint256 assetsOwed = market.borrowAtMaturity(maturity, assets / 2, type(uint256).max, ALICE, ALICE);
  assertEq(assetsOwed, 5076712328767123285000);
}
```

## Impact

User borrows and places the protocol at a significant risk with a very small interest rate.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L121](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L121>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L878](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L878>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1006](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1006>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1012](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1012>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1018](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L1018>)

## Recommendation

When assets are `0`, the interest rate should be the maximum. Additionally, when initializing, it's better to set the factor to some time in the past so the first depositor increases the utilization ratio accordingly.
