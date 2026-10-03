---
id: 25151
severity: "Medium"
---

# Market utilization ratio near 100% will DoS deposits as harvest tries to withdraw and reverts

## Description



## Proof of Concept

Add the following test to `StakedEXA.t.sol` as proof.

```solidity
function test_POC_DoSedDeposits_FailsAsMarketIsFullyUtilized() external {
  Auditor auditor = Auditor(address(new ERC1967Proxy(address (new Auditor(18)), "")));

  uint256 assets = 1e18;
  market = Market(address(new ERC1967Proxy(address(new Market(ERC20Solmate(address(providerAsset)), auditor)), "")));
  market.initialize(
    "STEXA",
    3,
    1e18,
    new InterestRateModel(
      IRMParameters({
        minRate: 3.5e16,
        naturalRate: 8e16,
        maxUtilization: 1.1e18,
        naturalUtilization: 0.75e18,
        growthSpeed: 1.1e18,
        sigmoidSpeed: 2.5e18,
        spreadFactor: 0.2e18,
        maturitySpeed: 0.5e18,
        timePreference: 0.01e18,
        fixedAllocation: 0.6e18,
        maxRate: 15_000e16
    }),
    Market(address(0))),
    0.02e18 / uint256(1 days),
    1e17,
    0,
    0.0046e18,
    0.42e18
  );

  auditor.initialize(Auditor.LiquidationIncentive(0, 0));
  auditor.enableMarket(market, MockPriceFeed(auditor.BASE_FEED()), 0.9e18);

  // FIX market change, another issue
  vm.prank(address(stEXA));
  providerAsset.approve(address(market), type(uint256).max);

  stEXA.setMarket(market);

  providerAsset.mint(PROVIDER, 1_000e18);

  vm.startPrank(PROVIDER);
  providerAsset.approve(address(market), type(uint256).max);
  market.deposit(1_000e18, PROVIDER);
  market.approve(address(stEXA), 1_000e18);
  vm.stopPrank();

  address user = makeAddr("user");
  providerAsset.mint(user, 1_000e18);
  vm.startPrank(user);
  providerAsset.approve(address(market), type(uint256).max);
  market.deposit(1_000e18, user);
  market.borrow(1_000e18*90*90/100/100, user, user);
  vm.stopPrank();

  // Random amount of time to make sure borrowed amount reaches deposits
  skip(1000 weeks);

  exa.mint(address(this), assets);

  vm.expectRevert();
  stEXA.deposit(assets, address(this));
}
```

## Recommendation

Cap the amount to withdraw to the maximum amount that does not revert, that is, the amount that makes the utilization ratio reach 100% but not over it.
