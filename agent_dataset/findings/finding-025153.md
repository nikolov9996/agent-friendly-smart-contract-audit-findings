---
id: 25153
severity: "Medium"
---

# Setting a new market will make depositing to the market impossible when harvesting, DoSing deposits

## Description



## Proof of Concept

```solidity
function test_POC_DoSedDeposits_DueToSettingANewMarket() external {
  bool triggerRevert = true;

  uint256 assets = 1e18;
  market = Market(address(new ERC1967Proxy(address(new Market(ERC20Solmate(address(providerAsset)), new Auditor(18))), "")));
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
  market.grantRole(market.PAUSER_ROLE(), address(this));

  // FIX market change
  if (!triggerRevert) {
    vm.prank(address(stEXA));
    providerAsset.approve(address(market), type(uint256).max);
  }

  stEXA.setMarket(market);

  providerAsset.mint(PROVIDER, 1_000e18);

  vm.startPrank(PROVIDER);
  providerAsset.approve(address(market), type(uint256).max);
  market.deposit(1_000e18, PROVIDER);
  market.approve(address(stEXA), 1_000e18);
  vm.stopPrank();

  exa.mint(address(this), assets);

  if (triggerRevert) vm.expectRevert();
  stEXA.deposit(assets, address(this));
}
```

## Recommendation

Do the same as in the constructor and approve the new `Market` when `setMarket()` is called with `type(uint256).max` `market.asset()` assets.
