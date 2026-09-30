---
id: 2829
severity: "Medium"
---

# Incorrect Total Assets Calculation in _harvestAndReport Leading to Share Value Manipulation and Irredeemable Assets

## Description

The harvestAndReport() includes underlying assets (which can be directly transferred into the strategy (WETH)) in total assets calculation, leading to inflated profit reporting and share dilution during report(). These directly transferred underlying assets (WETH) become irredeemable since they are not recorded in the transmuter and the strategy can only claim amountClaim deposited amount on the transmuter which can then be swapped.

While the known issue reported cases that are associated with asset balance on all the strategies, this report deals with underlying assets on the strategy and how the accounting of underlying assets directly affects the shares of the Strategies.

The _harvestAndReport() function incorrectly includes the strategy's underlying token balance:

```solidity
function _harvestAndReport()
    internal
    override
    returns (uint256 _totalAssets)
{
    uint256 unexchanged = transmuter.getUnexchangedBalance(address(this));
    uint256 underlyingBalance = underlying.balanceOf(address(this));
    _totalAssets = unexchanged + asset.balanceOf(address(this)) + underlyingBalance; // @audit
}
```

The issue arises because:
Only WETH claimed from the transmuter can be swapped to alETH via claimAndSwap:

```solidity
function claimAndSwap(
    uint256 _amountClaim, 
    uint256 _minOut, 
    uint256 _routeNumber
) external onlyKeepers {

    transmuter.claim(_amountClaim, address(this));

    uint256 balBefore = asset.balanceOf(address(this));

    require(minOut > amountClaim, "minOut too low");

    router.exchange(
        routes[_routeNumber],
        swapParams[_routeNumber],
        _amountClaim,
        _minOut,
        pools[_routeNumber],
        address(this)
    );        
    uint256 balAfter = asset.balanceOf(address(this));
    
    require((balAfter - balBefore) >= _minOut, "Slippage too high");

    transmuter.deposit(asset.balanceOf(address(this)), address(this));
}
```

When WETH is directly transferred to the strategy:
It's counted in _harvestAndReport() as profit
This inflated profit leads to share minting in TokenizedStrategy during reporting

```solidity
function report()
    external
    nonReentrant
    onlyKeepers
    returns (uint256 profit, uint256 loss)
{
    // Cache storage pointer since its used repeatedly.
    StrategyData storage S = _strategyStorage();

    // Tell the strategy to report the real total assets it has.
    // It should do all reward selling and redepositing now and
    // account for deployed and loose asset so we can accurately
    // account for all funds including those potentially airdropped
    // and then have any profits immediately locked.
    uint256 newTotalAssets = IBaseStrategy(address(this))
        .harvestAndReport();

    uint256 oldTotalAssets = _totalAssets(S);

    // some codes....

    // Calculate profit/loss.
    if (newTotalAssets > oldTotalAssets) {
      // some codes...
      // Mint shares based on inflated profit calculation
      _mint(S, protocolFeesRecipient, protocolFeeShares);
      _mint(S, S.performanceFeeRecipient, totalFeeShares - protocolFeeShares);
     // some codes...
    }
  // some codes...
}
```

The directly transferred underlying assets becomes irredeemable because:
It's not recorded in the transmuter
It can't be swapped through claimAndSwap as shown above
The strategy has no mechanism to handle these "orphaned" funds
Share Dilution:
Existing users' shares are diluted when directly transferred WETH is counted as profit without been account for neither can it be withdrawn
This leads to incorrect share price calculations
Irredeemable Assets:
Creates a discrepancy between reported and actually available assets

```solidity
function availableWithdrawLimit(
        address /*_owner*/
    ) public view override returns (uint256) {
        // returns the asset balance and unexchanged balance
        return asset.balanceOf(address(this)) + transmuter.getUnexchangedBalance(address(this));
    }
```

Incorrect Fee Distribution:
Performance and protocol fees are calculated on inflated profits
Fee recipients receive shares backed by assets that can't be redeemed

## Proof of Concept

```solidity
function testgainFeesWhenunderlyingassetdirectkytransferaffectingothers(
    address _address,
    uint16 _profitFactor
) public {
    uint128 _amount = 1e18;
    profitFactor = uint16(bound(uint256(profitFactor), 10, MAX_BPS));
    vm.assume(
        _address != address(0) &&
            _address != address(strategy) &&
            _address != protocolFeeRecipient &&
            _address != performanceFeeRecipient &&
            _address != address(yieldSource)
    );

    strategy = IMockStrategy(address(strategyMainnet));
    setUpMainnetStrategy(strategy);
    // reset fees
    uint16 protocolFee = 1_000;
    uint16 performanceFee = 1_000;
    setFees(protocolFee, performanceFee);
    
    vm.prank(management);
    strategy.setPerformanceFee(performanceFee);

    // Set max unlocking time to 0.
    vm.prank(management);
    strategy.setProfitMaxUnlockTime(0);
    assertEq(strategy.profitMaxUnlockTime(), 0);

    mintAndDepositIntoStrategy(strategy, address, amount);
    // Increase time to simulate interest being earned
    increaseTimeAndCheckBuffer(strategy, profitMaxUnlockTime, 0);

    uint256 profit = (amount * profitFactor) / MAX_BPS;
    uint256 expectedPerformanceFee = (profit * performanceFee) / MAX_BPS;
    uint256 expectedProtocolFee = (expectedPerformanceFee * protocolFee) /
        MAX_BPS;
    expectedPerformanceFee -= expectedProtocolFee;

    uint256 totalExpectedFees = expectedPerformanceFee +
        expectedProtocolFee;
    
    asset.mint(address(strategy), profit);

    // inflate the strategy with profit
    undelyingAsset.mint(address(strategy), profit);

    uint256 strategyBalanceOfAddressBefore = strategy.maxRedeem(_address);

    vm.prank(keeper);
    (uint256 _profit, ) = strategy.report();

    uint256 strategyBalanceOfAddress = strategy.maxRedeem(_address);
    
    // protocolFeesRecipient redeemed his share of the profit
    (
        ,
        address protocolFeesRecipient
    ) = mockFactory.protocolfeeconfig();
    vm.prank(protocolFeesRecipient);
    strategy.redeem(strategy.maxRedeem(protocolFeesRecipient), protocolFeesRecipient, protocolFeesRecipient);
    
    // performanceFeeRecipient redeemed his share of the profit
    vm.prank(performanceFeeRecipient);
    strategy.redeem(strategy.maxRedeem(performanceFeeRecipient), performanceFeeRecipient, performanceFeeRecipient);
    
    // this user shares will reduce because of the underllying asset transfer that was is
    // recorded in the strategy nor in the transmuter
    vm.prank(_address);
    strategy.redeem(strategyBalanceOfAddressBefore, address, address); // an attempt to withdraw balance before will fail
}
```

## Recommendation

Either Remove underlying balance from total assets calculation:

```solidity
function _harvestAndReport()
    internal
    override
    returns (uint256 _totalAssets)
{
    uint256 unexchanged = transmuter.getUnexchangedBalance(address(this));
    _totalAssets = unexchanged + asset.balanceOf(address(this));
}
```

Or during claimAndSwap, account for underlying asset balance of strategy:

```solidity
function claimAndSwap(
    uint256 _amountClaim, 
    uint256 _minOut, 
    uint256 _routeNumber
) external onlyKeepers {

    transmuter.claim(_amountClaim, address(this));

    uint256 balBefore = asset.balanceOf(address(this));
    
    uint256 totalSwapAmount = underlying.balanceOf(address(this)) + _amountClaim; // @audit

    require(_minOut > totalSwapAmount, "minOut too low");

    router.exchange(
        routes[_routeNumber],
        swapParams[_routeNumber],
        totalSwapAmount,
        _minOut,
        pools[_routeNumber],
        address(this)
    );        
    uint256 balAfter = asset.balanceOf(address(this));
    
    require((balAfter - balBefore) >= _minOut, "Slippage too high");

    transmuter.deposit(asset.balanceOf(address(this)), address(this));
}
```

tokenizedStrategy contract: https://github.com/yearn/tokenized-strategy/blob/9ef68041bd034353d39941e487499d111c3d3901/src/TokenizedStrategy.sol#L1095

Transmutter: https://github.com/alchemix-finance/v2-foundry/blob/master/src/TransmuterV2.sol

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting flaw in the strategy’s _harvestAndReport function where the balance of the underlying token (WETH) held directly by the strategy contract is added to the total assets together with the transmuter‑unexchanged balance and the already‑wrapped asset balance. This causes the reported total assets to be higher than the amount that can actually be redeemed because the underlying tokens are not recorded in the Transmuter and cannot be swapped to the target asset through claimAndSwap. When an external account transfers WETH directly to the strategy, the extra amount is counted as profit during the subsequent report() call. The report logic then mints new shares for protocol and performance fee recipients based on this inflated profit, which dilutes existing shareholders and leads to an incorrect share‑price calculation. The underlying WETH remains orphaned: it is included in the asset balance shown to users but is excluded from the withdraw limit calculation and cannot be claimed, making it effectively irredeemable. Users therefore may see their share value drop, receive zero or reduced payouts when attempting to redeem, and observe fees being taken from phantom gains. The issue manifests only when the strategy receives direct transfers of the underlying token; normal operation through the Transmuter does not expose the bug. It was discovered during a manual audit that flagged the line adding underlyingBalance to _totalAssets. The problem is subtle because the contract’s availableWithdrawLimit function aggregates only the wrapped asset balance and the transmuter balance, so the extra underlying tokens are hidden from the withdrawal path while still inflating profit reports. To remediate, the underlying balance should be excluded from the total‑assets calculation, or the claimAndSwap routine should be extended to incorporate the underlying token amount so that it can be properly exchanged and deposited. This class of bug belongs to the broader category of incorrect total‑asset accounting leading to share‑value manipulation and unrecoverable funds.
