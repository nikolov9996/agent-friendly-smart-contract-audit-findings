---
id: 25166
severity: "Medium"
---

# Rewards can disappear when new rewards are distributed in the RewardsController.

## Description



## Proof of Concept

## Vulnerability Detail

The `rewards distribution config` includes a `start time` and `duration`.

```solidity
struct Config {
  Market market;
  ERC20 reward;
  IPriceFeed priceFeed;
  uint32 start;   // @audit, here
  uint256 distributionPeriod;   // @audit, here
  uint256 targetDebt;
  uint256 totalDistribution;
  uint256 undistributedFactor;
  int128 flipSpeed;
  uint64 compensationFactor;
  uint64 transitionFactor;
  uint64 borrowAllocationWeightFactor;
  uint64 depositAllocationWeightAddend;
  uint64 depositAllocationWeightFactor;
}
```

Whenever a `borrower` changes his `balance`, we update the `rewards index` for that `borrower` and calculate the `unclaimed rewards`.

```solidity
function handleBorrow(address account) external {
  Market market = Market(msg.sender);
  AccountOperation[] memory ops = new AccountOperation[](1);
  (, , uint256 accountFloatingBorrowShares) = market.accounts(account);

  Distribution storage dist = distribution[market];
  uint256 available = dist.availableRewardsCount;
  for (uint128 r = 0; r < available; ) {
    ERC20 reward = dist.availableRewards[r];
    ops[0] = AccountOperation({
      operation: true,
      balance: accountFloatingBorrowShares + accountFixedBorrowShares(market, account, dist.rewards[reward].start)
    });
    update(account, Market(msg.sender), reward, ops);  // @audit, here
    unchecked {
      ++r;
    }
  }
}
```

There are two types of `borrow shares`: `floating shares` and `fixed shares`. The calculation for `fixed shares` is based on the `rewards distribution start time`.

```solidity
function previewAllocation(
  RewardData storage rewardData,
  Market market,
  uint256 deltaTime
) internal view returns (uint256 borrowIndex, uint256 depositIndex, uint256 newUndistributed) {
  TotalMarketBalance memory m;
  m.floatingDebt = market.floatingDebt();
  m.floatingAssets = market.floatingAssets();
  TimeVars memory t;
  t.start = rewardData.start;
  t.end = rewardData.end;
  {
    uint256 firstMaturity = t.start - (t.start % FixedLib.INTERVAL) + FixedLib.INTERVAL;  // @audit, here
    uint256 maxMaturity = block.timestamp -
      (block.timestamp % FixedLib.INTERVAL) +
      (FixedLib.INTERVAL * market.maxFuturePools());
    uint256 fixedDebt;
    for (uint256 maturity = firstMaturity; maturity <= maxMaturity; ) {  // @audit, here
      (uint256 borrowed, ) = market.fixedPoolBalance(maturity);
      fixedDebt += borrowed;
      unchecked {
        maturity += FixedLib.INTERVAL;
      }
    }
    m.debt = m.floatingDebt + fixedDebt;
    m.fixedBorrowShares = market.previewRepay(fixedDebt);
  }
}
```

Now, suppose there are new upcoming `rewards`, and the `rewards distribution` is scheduled for the future. In this case, the `start time` will be updated with the new value,

```solidity
function config(Config[] memory configs) external onlyRole(DEFAULT_ADMIN_ROLE) {
    if (block.timestamp < end) {
      uint256 released = 0;
      uint256 elapsed = 0;
      if (block.timestamp > start) {
        released =
          rewardData.lastConfigReleased +
          rewardData.releaseRate *
          (block.timestamp - rewardData.lastConfig);
        elapsed = block.timestamp - start;
        if (configs[i].totalDistribution <= released || configs[i].distributionPeriod <= elapsed) {
          revert InvalidConfig();
        }
        rewardData.lastConfigReleased = released;
      }

      rewardData.releaseRate =
        (configs[i].totalDistribution - released) /
        (configs[i].distributionPeriod - elapsed);
    } else if (rewardData.start != configs[i].start) {
      rewardData.start = configs[i].start;  // @audit, here
      rewardData.lastUpdate = configs[i].start;
      rewardData.releaseRate = configs[i].totalDistribution / configs[i].distributionPeriod;
      rewardData.lastConfigReleased = 0;
    }
  }
}
```

The issue is that the `fixed borrow shares` from the `old start time` to the `new start time` are removed in the `rewards calculation`.

```solidity
function accountFixedBorrowShares(
  Market market,
  address account,
  uint32 start
) internal view returns (uint256 fixedDebt) {
  uint256 firstMaturity = start - (start % FixedLib.INTERVAL) + FixedLib.INTERVAL;  // @audit, here
  uint256 maxMaturity = block.timestamp -
    (block.timestamp % FixedLib.INTERVAL) +
    (FixedLib.INTERVAL * market.maxFuturePools());

  for (uint256 maturity = firstMaturity; maturity <= maxMaturity; ) {  // @audit, here
    (uint256 principal, ) = market.fixedBorrowPositions(maturity, account);
    fixedDebt += principal;
    unchecked {
      maturity += FixedLib.INTERVAL;
    }
  }
  fixedDebt = market.previewRepay(fixedDebt);
}
```

It's important to note that these `shares` are actually part of the previous `rewards distribution`, but `borrowers` may not have updated their `rewards` in time.

Let's consider an example. Two `borrowers`, `BOB` and `ALICE`, engage in borrowing operations. They `borrow` funds at `maturity` periods of `4 weeks`, `12 weeks` and `16 weeks`. The current `rewards distribution` starts at time `0` and lasts for `12 weeks`.

Both `borrowers` have the same `claimable rewards` amount obviously. `BOB` `claims` his `rewards` after `18 weeks` pass, but `ALICE` delays `claiming`. Meanwhile, the `admin` sets a new `start date` for upcoming `rewards`.

When `ALICE` finally claims her `rewards`, the `fixed borrow shares` before this `new start date` are removed from the calculation. Consequently, she loses a significant portion of her `rewards`. Specific values can be described in the below `log`.

```solidity
block.timestamp                ==>   0
usdcConfig.start               ==>   0
usdcConfig.distributionPeriod  ==>   12 weeks
*******************
block.timestamp                ==>   4838400
*******************
block.timestamp                ==>   10886400
Claimable for ALICE            ==>   999999975000000000000
Claimable for BOB              ==>   999999975000000000000
*******************
Reward Balance for BOB         ==>   999999975000000000000
Reward Balance for ALICE       ==>   734619963000000000000
```

Please add below test to the `RewardsController.t.sol`.

```solidity
function testResetConfig () external {
  vm.prank(ALICE);
  marketUSDC.approve(address(this), 100 ether);

  vm.prank(BOB);
  marketUSDC.approve(address(this), 100 ether);

  vm.prank(ALICE);
  auditor.enterMarket(marketUSDC);

  vm.prank(BOB);
  auditor.enterMarket(marketUSDC);

  marketUSDC.deposit(50 ether, ALICE);
  marketUSDC.deposit(50 ether, BOB);

  RewardsController.Config memory usdcConfig = rewardsController.rewardConfig(marketUSDC, opRewardAsset);

  console2.log("block.timestamp                ==>  ", block.timestamp);
  console2.log("usdcConfig.start               ==>  ", usdcConfig.start);
  console2.log("usdcConfig.distributionPeriod  ==>  ", usdcConfig.distributionPeriod / 1 weeks, "weeks");
  assertEq(usdcConfig.distributionPeriod, 12 weeks);

  marketUSDC.borrowAtMaturity(4 weeks, 1 ether, 20 ether, ALICE, ALICE);
  marketUSDC.borrowAtMaturity(4 weeks, 1 ether, 20 ether, BOB, BOB);

  console2.log("*******************");
  vm.warp(8 weeks);
  console2.log("block.timestamp                ==>  ", block.timestamp);
  marketUSDC.borrowAtMaturity(12 weeks, 1 ether, 20 ether, ALICE, ALICE);
  marketUSDC.borrowAtMaturity(12 weeks, 1 ether, 20 ether, BOB, BOB);
  marketUSDC.borrowAtMaturity(16 weeks, 2 ether, 20 ether, ALICE, ALICE);
  marketUSDC.borrowAtMaturity(16 weeks, 2 ether, 20 ether, BOB, BOB);

  console2.log("*******************");
  vm.warp(18 weeks);
  console2.log("block.timestamp                ==>  ", block.timestamp);
  console2.log("Claimable for ALICE            ==>  ", rewardsController.allClaimable(ALICE, opRewardAsset));
  console2.log("Claimable for BOB              ==>  ", rewardsController.allClaimable(BOB, opRewardAsset));

  vm.prank(BOB);
  rewardsController.claimAll(BOB);

  opRewardAsset.mint(address(rewardsController), 4_000 ether);
  RewardsController.Config[] memory configs = new RewardsController.Config[](1);
  configs[0] = RewardsController.Config({
    market: marketUSDC,
    reward: opRewardAsset,
    priceFeed: MockPriceFeed(address(0)),
    targetDebt: 20_000e6,
    totalDistribution: 2_000 ether,
    start: uint32(block.timestamp),
    distributionPeriod: 12 weeks,
    undistributedFactor: 0.5e18,
    flipSpeed: 2e18,
    compensationFactor: 0.85e18,
    transitionFactor: 0.64e18,
    borrowAllocationWeightFactor: 0,
    depositAllocationWeightAddend: 0.02e18,
    depositAllocationWeightFactor: 0.01e18
  });
  rewardsController.config(configs);

  vm.prank(ALICE);
  rewardsController.claimAll(ALICE);

  console2.log("*******************");
  console2.log("Reward Balance for BOB         ==>  ", opRewardAsset.balanceOf(BOB));
  console2.log("Reward Balance for ALICE       ==>  ", opRewardAsset.balanceOf(ALICE));
}
```

## Impact

The `admin` can not consider whether all `borrowers` have already `claimed` their `rewards` before setting a `new rewards start time` so this can happen easily.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L826-L827](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L826-L827>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L78](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L78>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L481-L495](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L481-L495>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L693-L694](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L693-L694>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L367](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/RewardsController.sol#L367>)

## Recommendation

No recommendation provided.
