---
id: 18133
severity: "High"
---

# StabilizerNode.stabilize uses stale GlobalImpliedCollateralService data, which will make stabilize incorrect

## Description

In StabilizerNode.stabilize, `impliedCollateralService.syncGlobalCollateral()` is called only at the end of the function to synchronize the GlobalImpliedCollateralService data.

```solidity
if (!_shouldAdjustSupply(exchangeRate, stabilizeToPeg)) {
  lastStabilize = block.timestamp;
  impliedCollateralService.syncGlobalCollateral();
  return;
}
...
if (trackAfterStabilize) {
  maltDataLab.trackPool();
}
impliedCollateralService.syncGlobalCollateral();
lastStabilize = block.timestamp;
```

syncGlobalCollateral will use the data in `getCollateralizedMalt()`, which includes the collateralToken balance in overflowPool/swingTraderManager/liquidityExtension and the malt balance in swingTraderManager.

```solidity
function syncGlobalCollateral() public onlyActive {
  globalIC.sync(getCollateralizedMalt());
}
...
function getCollateralizedMalt() public view returns (PoolCollateral memory) {
  uint256 target = maltDataLab.priceTarget();

  uint256 unity = 10**collateralToken.decimals();

  // Convert all balances to be denominated in units of Malt target price
  uint256 overflowBalance = maltDataLab.rewardToMaltDecimals((collateralToken.balanceOf(
    address(overflowPool)
  ) * unity) / target);
  uint256 liquidityExtensionBalance = (collateralToken.balanceOf(
    address(liquidityExtension)
  ) * unity) / target;
  (
    uint256 swingTraderMaltBalance,
    uint256 swingTraderBalance
  ) = swingTraderManager.getTokenBalances();
  swingTraderBalance = (swingTraderBalance * unity) / target;
```

Since StabilizerNode.stabilize will use the results of maltDataLab.getActualPriceTarget/getSwingTraderEntryPrice to stabilize, and maltDataLab.getActualPriceTarget/getSwingTraderEntryPrice will use `GlobalImpliedCollateralService.collateralRatio`, to ensure correct stabilization, the data in GlobalServiceImpliedCollateralService should be the latest.

```solidity
function getActualPriceTarget() external view returns (uint256) {
  uint256 unity = 10**collateralToken.decimals();
  uint256 icTotal = maltToRewardDecimals(globalIC.collateralRatio());
...
function getSwingTraderEntryPrice()
  external
  view
  returns (uint256 stEntryPrice)
{
  uint256 unity = 10**collateralToken.decimals();
  uint256 icTotal = maltToRewardDecimals(globalIC.collateralRatio());
```

But since `impliedCollateralService.syncGlobalCollateral()` is not called before StabilizerNode.stabilize calls maltDataLab.getActualPriceTarget/getSwingTraderEntryPrice, this will cause StabilizerNode.stabilize to use stale GlobalImpliedCollateralService data, which will make stabilize incorrect.

A simple example would be:

1. `impliedCollateralService.syncGlobalCollateral()` is called to synchronize the latest data
2. SwingTraderManager.delegateCapital is called, and the collateralToken is taken out from SwingTrader, which will make the `GlobalImpliedCollateralService.collateralRatio` larger than the actual collateralRatio.

```solidity
function delegateCapital(uint256 amount, address destination)
  external
  onlyRoleMalt(CAPITAL_DELEGATE_ROLE, "Must have capital delegation privs")
  onlyActive
{
  collateralToken.safeTransfer(destination, amount);
  emit Delegation(amount, destination, msg.sender);
}
...
function collateralRatio() public view returns (uint256) {
  uint256 decimals = malt.decimals();
  uint256 totalSupply = malt.totalSupply();
  if (totalSupply == 0) {
    return 0;
  }
  return (collateral.total * (10**decimals)) / totalSupply; // @audit: collateral.total is larger than the actual
}
```

3. When StabilizerNode.stabilize is called, it will use the stale collateralRatio for calculation. If the collateralRatio is too large, the results of maltDataLab.getActualPriceTarget/getSwingTraderEntryPrice will be incorrect, thus making stabilize incorrect.

Since stabilize is a core function of the protocol, stabilizing with the wrong data is likely to cause malt to be depegged, so the vulnerability should be High risk.

## Proof of Concept

no poc

## Recommendation

Call `impliedCollateralService.syncGlobalCollateral()` before StabilizerNode.stabilize calls maltDataLab.getActualPriceTarget.

```solidity
function stabilize() external nonReentrant onlyEOA onlyActive whenNotPaused {
  // Ensure data consistency
  maltDataLab.trackPool();

  // Finalize auction if possible before potentially starting a new one
  auction.checkAuctionFinalization();

  impliedCollateralService.syncGlobalCollateral();

  require(
    block.timestamp >= stabilizeWindowEnd || _stabilityWindowOverride(),
    "Can't call stabilize"
  );
  stabilizeWindowEnd = block.timestamp + stabilizeBackoffPeriod;

  // used in 3 location.
  uint256 exchangeRate = maltDataLab.maltPriceAverage(priceAveragePeriod);
  bool stabilizeToPeg = onlyStabilizeToPeg; // gas

  if (!_shouldAdjustSupply(exchangeRate, stabilizeToPeg)) {
    lastStabilize = block.timestamp;
    impliedCollateralService.syncGlobalCollateral();
    return;
  }

  emit Stabilize(block.timestamp, exchangeRate);

  (uint256 livePrice, ) = dexHandler.maltMarketPrice();

  uint256 priceTarget = maltDataLab.getActualPriceTarget();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a data‑staleness bug in the StabilizerNode contract. The core stabilize function reads the global collateral ratio from the GlobalImpliedCollateralService to computethe target price and the swing‑trader entry price, but the service is only synchronized after those reads. Because syncGlobalCollateral is invoked at the end of stabilize (or only in early‑exit paths), any state change that modifies the collateral balance – for example a delegateCapital call that moves collateral out of the SwingTraderManager – leaves the global collateral ratio outdated. When stabilize subsequently uses the stale ratio, the calculated price target can be too high or too low, causing the protocol to adjust the Malt supply based on incorrect data. This can push the Malt token off its peg, effectively de‑pegging the stablecoin and exposing users to loss of value. The bug occurs whenever a collateral‑affecting operation happens between the last synchronization and a call to stabilize, which is common in normal protocol operation. It affects all token holders, liquidity providers, and any party relying on the peg, because the protocol may mint or burn an incorrect amount of Malt. The issue was discovered during a formal audit by Code4rena, where the control‑flow was examined and it was noted that the global collateral service is not refreshed before the price calculations. The problem is subtle because the contract does call syncGlobalCollateral, but the call is placed after the critical calculations, making the inconsistency easy to miss in a quick code review. The recommended fix is to invoke impliedCollateralService.syncGlobalCollateral() before any call to maltDataLab.getActualPriceTarget or getSwingTraderEntryPrice, ensuring that the collateral ratio reflects the latest state. In broader terms, the bug is a classic stale‑state or race‑condition vulnerability where a contract relies on outdated on‑chain data to make financial decisions, violating the protocol’s accounting invariants and jeopardizing its stability.
