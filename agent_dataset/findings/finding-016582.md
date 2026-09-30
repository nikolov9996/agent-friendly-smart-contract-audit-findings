---
id: 16582
severity: "Medium"
---

# Liquidating positions of different accounts for the same market on the same block.timestamp uses the same fundingFeePerUnit regardless of the computed MarkPrice based on the size of the position been liqudiated.

## Description

When liquidating multiple accounts in the same tx, the fundingFeePerUnit that will be used to compute the fundingFee is erroneously calculated for all the accounts starting from the 2nd liquidated account. 
The fundingFeePerUnit of all the liquidated accounts will be the same fundingFeePerUnit as the one computed for the first liquidated account, regardless of the position size and mark price of each position being liquidated.

When liquidating accounts, it is possible to liquidate multiple accounts in the same tx, which means, the block.timestamp for all of these liquidations will be the same.

As part of the liquidation process, the logic computes the funding fee that the position being liquidated has accrued, either positive or negative. This fundingFee is derived from the fundingFeePerUnit, which the fundingFeePerUnit is computed from the lastFundingFeePerUnit and the pendingFundingFeePerUnit.
The pendingFundingFeePerUnit itself is derived from the average funding rate, the elapsed time since the last funding, and the current MarkPrice computed to reflect the change on the marked after closing the liquidated position.
The problem with the current way how the pendingFundingFeePerUnit is computed is that when liquidating more than 1 account at the same time, the pendingFundingFeePerUnit for the 2nd and the rest of the accounts will be 0, which means, the fundingFeePerUnitX18 for all the positions to be liquidated will be the same as the computed fundingFeePerUnitX18 of the 1st liquidated position.
This is clearly wrong since each position can have a different size and a different MarkPrice, but, regardless of that, the fundingFeePerUnitX18 would be the same for all the positions been liquidated.
This ends up causing the funding fee to be paid/earn is wrong.

Let's see where exactly the problem occurs, this is the execution trace call:
LiquidationBranch.liquidateAccounts() => TradingAccount.getAccountMarginRequirementUsdAndUnrealizedPnlUsd() => PerpetualMarket.getNextFundingFeePerUnit()
The nextFundingFeePerUnit is computed based on the current funding rate and the MarkPrice, which, the currentFundingRate is computed based on the lastFundingRate, the currentFundingVelocity and the elapsedTimeSinceLastFunding.
Here we encounter the first problem, the fundingRate will be returned as the lastFundingRate, no matter the currentFundingVelocity. The reason is that by multiplying currentFundingVelocity * elapsedTime, the result will be 0, because, elapsedTime is 0.

```solidity
function getCurrentFundingRate(Data storage self) internal view returns (SD59x18) {
    //@audit => For the 2nd and rest of positions been liquidated, currentFundingRate will be the lastFundingRate, regardless of the currentFundingVelocity.
    return sd59x18(self.lastFundingRate).add(
        //@audit => Multipltying currentFundingVelocity times 0 will return 0.
        getCurrentFundingVelocity(self).mul(getProportionalElapsedSinceLastFunding(self).intoSD59x18())
    );
}

function getProportionalElapsedSinceLastFunding(Data storage self) internal view returns (UD60x18) {
    //@audit => When liquidating multiple account, the lastFundingTime of the 2nd and the rest of positions in the same market will be block.timestamp, so, this will return 0
    //@audit => block.timestamp - block.timestamp === 0.
    return ud60x18Convert(block.timestamp - self.lastFundingTime).div(
        ud60x18Convert(Constants.PROPORTIONALFUNDINGPERIOD)
    );
}
```
Now, when computing the nextFeePerUnit, we'll see why the value for the 2nd and rest of positions will be the same as the one computed for the first position.
The nextFeePerUnit will be only the lastFundingFeePerUnit, because the pendingFeePerUnit will be computed as 0, for the same reason the funding rate is also computed as 0.

```solidity
function getNextFundingFeePerUnit(
        Data storage self,
        SD59x18 fundingRate,
        UD60x18 markPriceX18
    )
        ...
    {
        //@audit => The returned value for the 2nd and rest of accounts will be lastFundingFeePerUnit. pendingFundingFeePerUnit will be 0
        return sd59x18(self.lastFundingFeePerUnit).add(getPendingFundingFeePerUnit(self, fundingRate, markPriceX18));
    }

function getPendingFundingFeePerUnit(
        Data storage self,
        SD59x18 fundingRate,
        UD60x18 markPriceX18
    )
        ...
    {

        SD59x18 avgFundingRate = unary(sd59x18(self.lastFundingRate).add(fundingRate)).div(sd59x18Convert(2));

        //@audit => getProportionalElapsedSinceLastFunding() will return 0, so, anything multiplied by 0 is 0.
        return avgFundingRate.mul(getProportionalElapsedSinceLastFunding(self).intoSD59x18()).mul(
            markPriceX18.intoSD59x18()
        );

        //@audit-issue => Regardless of the funding rate and mark price, the returned pendingFundingFeePerUnit will be 0!
    }
```

Finally, now that we've seen the fundingFeePerUnit would be the same for all the positions, regardless of their size, let's see how the fundingFeePerUnit impacts the actual funding fee to pay/earn.

```solidity
function getAccountMarginRequirementUsdAndUnrealizedPnlUsd(
    Data storage self,
    uint128 targetMarketId,
    SD59x18 sizeDeltaX18
)
    ...
{
    ...

    for (uint256 i; i < cachedActiveMarketsIdsLength; i++) {
        ...

        // calculate price impact as if trader were to close the entire position
        UD60x18 markPrice = perpMarket.getMarkPrice(sd59x18(-position.size), perpMarket.getIndexPrice());

        //@audit-issue => fundingFeePerUnit for all the liquidated positions will be the same as the fundingFeePerUnit of the first liquidated position, regardless of the current funding rate and mark price of each of the positions been liquidated.
        // get funding fee per unit
        SD59x18 fundingFeePerUnit =
            perpMarket.getNextFundingFeePerUnit(perpMarket.getCurrentFundingRate(), markPrice);

       ...

        //@audit-issue => Using an incorrect fundingFeePerUnit will ends up computing a wrong accrued funding fee, which it will impact the calculation of the uPnL.
        // get unrealized pnl + accrued funding fees
        SD59x18 positionUnrealizedPnl =
            position.getUnrealizedPnl(markPrice).add(position.getAccruedFunding(fundingFeePerUnit));

        ...
    }
}
```

Coded PoC
I coded a PoC to demonstrate the problem about all accounts been liquidated using the same fundingFeePerUnit.

We'll need to add a couple of console.log statements to the TradingAccount.sol and LiquidationBranch.sol files, so we can see the exact values when the functions are called.

First, help me to add the next lines on the TradingAccount.sol file:
```solidity
import { console2 } from "forge-std/Test.sol";

library TradingAccount {

  ...

  function getAccountUnrealizedPnlUsd(Data storage self) internal view returns (SD59x18 totalUnrealizedPnlUsdX18) {
      uint256 cachedActiveMarketsIdsLength = self.activeMarketsIds.length();

      for (uint256 i; i < cachedActiveMarketsIdsLength; i++) {
         ...

          SD59x18 fundingFeePerUnitX18 = perpMarket.getNextFundingFeePerUnit(fundingRateX18, markPriceX18);
console2.log("Data of MarketID: ", marketId);
console2.log("======> fundingFeePerUnitX18: ", fundingFeePerUnitX18.intoInt256());

         ...
      }
  }

  ...

  function getAccountMarginRequirementUsdAndUnrealizedPnlUsd(
        Data storage self,
        uint128 targetMarketId,
        SD59x18 sizeDeltaX18
    )
        ...
    {
        ...

        for (uint256 i; i < cachedActiveMarketsIdsLength; i++) {
            ...

            // get funding fee per unit
            SD59x18 fundingFeePerUnit =
                perpMarket.getNextFundingFeePerUnit(perpMarket.getCurrentFundingRate(), markPrice);
console2.log("Values while liquidating in Market ID: ", perpMarket.id);
console2.log("======> fundingFeePerUnit: ", fundingFeePerUnit.intoInt256());

            ...
        }
    }

}
```

Now, help me to add the next lines on the LiquidationBranch.sol file:
```solidity
import { console2 } from "forge-std/Test.sol";

contract LiquidationBranch {

  ...

  function liquidateAccounts(uint128[] calldata accountsIds) external {
      ...
      for (uint256 i; i < accountsIds.length; i++) {
        console2.log("===============================================");
        // store current accountId being liquidated in working data
        ctx.tradingAccountId = accountsIds[i];
console2.log("  Liquidation data of account: ", ctx.tradingAccountId);

        ...
        ...
        ...
      }
    }

  ...
}
```

Finally, let's add the below PoC to the liquidateAccounts.t.sol test file:

```solidity
// Make sure to add the console2 log dependency at the very top
import { console2 } from "forge-std/Test.sol";

contract LiquidateAccountsIntegrationTest is Base_Test {
  ...

  //PoC
  function test_sameFundingFeeForOperationOnSameBlockTimestampPoC()
      external
      givenTheSenderIsARegisteredLiquidator
      whenTheAccountsIdsArrayIsNotEmpty
      givenAllAccountsExist
  {
      uint256 marketId = 3;
      uint256 secondMarketId = 5;
      bool isLong = true;
      uint256 timeDelta = 1 weeks;

      TestFuzzGivenThereAreLiquidatableAccountsInTheArrayContext memory ctx;

      ctx.fuzzMarketConfig = getFuzzMarketConfig(marketId);
      ctx.secondMarketConfig = getFuzzMarketConfig(secondMarketId);

      vm.assume(ctx.fuzzMarketConfig.marketId != ctx.secondMarketConfig.marketId);

      uint256 amountOfTradingAccounts = 2;

      ctx.marginValueUsd = 10_000e18 / amountOfTradingAccounts;
      ctx.initialMarginRate = ctx.fuzzMarketConfig.imr;

      deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd });

      // last account id == 0
      ctx.accountsIds = new uint128[](amountOfTradingAccounts);

      ctx.accountMarginValueUsd = ctx.marginValueUsd / (amountOfTradingAccounts + 1);

      //@audit => Open two positions on two different markets for Account1
      {
          ctx.tradingAccountId = createAccountAndDeposit(ctx.accountMarginValueUsd, address(usdz));

          openPosition(
              ctx.fuzzMarketConfig,
              ctx.tradingAccountId,
              ctx.initialMarginRate,
              ctx.accountMarginValueUsd / 2,
              isLong
          );

          openPosition(
              ctx.secondMarketConfig,
              ctx.tradingAccountId,
              ctx.secondMarketConfig.imr,
              ctx.accountMarginValueUsd / 2,
              isLong
          );

          ctx.accountsIds[0] = ctx.tradingAccountId;

          deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd });
      }

      //@audit => Open two positions on two different markets for Account2
      //@audit => The size of these positions is twice as big as the size of the positions of the account1!
      {
          ctx.tradingAccountId = createAccountAndDeposit(ctx.accountMarginValueUsd * 2, address(usdz));

          openPosition(
              ctx.fuzzMarketConfig,
              ctx.tradingAccountId,
              ctx.initialMarginRate,
              ctx.accountMarginValueUsd,
              isLong
          );

          openPosition(
              ctx.secondMarketConfig,
              ctx.tradingAccountId,
              ctx.secondMarketConfig.imr,
              ctx.accountMarginValueUsd,
              isLong
          );

          ctx.accountsIds[1] = ctx.tradingAccountId;

          deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd});
      }

      setAccountsAsLiquidatable(ctx.fuzzMarketConfig, isLong);
      setAccountsAsLiquidatable(ctx.secondMarketConfig, isLong);

      changePrank({ msgSender: liquidationKeeper });

      skip(timeDelta);

      SD59x18 totalUnrealizedPnlUsdX18;

      console2.log("===============================================");
      console2.log("=========== Start of PoC Output ===============");
      console2.log("===============================================");

      //@audit => when getAccountTotalUnrealizedPnl() is called, the fundingFeePerUnit of each position will be shown on the console (Before liquidating)

      console2.log("          Data for Naruto user / Account 1");
      totalUnrealizedPnlUsdX18 = perpsEngine.getAccountTotalUnrealizedPnl(ctx.accountsIds[0]);
      //console2.log("totalUnrealizedPnlUsdX18: ", totalUnrealizedPnlUsdX18.intoInt256());

      console2.log("===============================================");
      console2.log("          Data for Sasuke user / Account 2");
      totalUnrealizedPnlUsdX18 = perpsEngine.getAccountTotalUnrealizedPnl(ctx.accountsIds[1]);
      //console2.log("totalUnrealizedPnlUsdX18: ", totalUnrealizedPnlUsdX18.intoInt256());

      console2.log("===============================================");
      //@audit => when liquidateAccounts() is called, the fundingFeePerUnit of each position will be shown on the console (during the liquidation)
      perpsEngine.liquidateAccounts(ctx.accountsIds);

      console2.log("===============================================");
      console2.log("============ End of PoC Output ===============");
      console2.log("===============================================");
  }

}
```

Run the Poc with the command forge test --match-test test_sameFundingFeeForOperationOnSameBlockTimestampPoC -vvv, and let's analyze the output:
As we can see, while the accounts are been liquidated, the fundingFeePerUnit of the two accounts is the same, regardless of the difference in the position size and the mark price.

  ===============================================
  =========== Start of PoC Output ===============
  ===============================================
  //@audit => Data before running the liquidation!
            Data for Naruto user / Account 1
  Data of MarketID:  3
  //@audit => fundingFeePerUnit of account1 on Market3 will be the same fundingFeePerUnit for all the liquidated accounts
  ======> fundingFeePerUnitX18:  -30419422517522

  Data of MarketID:  5
  //@audit => fundingFeePerUnit of account1 on Market5 will be the same fundingFeePerUnit for all the liquidated accounts
  ======> fundingFeePerUnitX18:  -26240866280127
  ===============================================
            Data for Sasuke user / Account 2
  //@audit => This is the fundingFeePerUnit that should be used when liquidating account2, but instead, it will use the fundingFeePerUnit of account1

  Data of MarketID:  3
  ======> fundingFeePerUnitX18:  -30419400850761

  Data of MarketID:  5
  ======> fundingFeePerUnitX18:  -26240866002832
  ===============================================
  ===============================================
  //@audit => Data while liquidating the accounts
    Liquidation data of account:  1
  Values while liquidating in Market ID:  3
  ======> fundingFeePerUnit:  -30419422517522

  Values while liquidating in Market ID:  5
  ======> fundingFeePerUnit:  -26240866280127
  ===============================================
    Liquidation data of account:  2
  Values while liquidating in Market ID:  3
  //@audit => Same fundingFeePerUnit as the account1 in Market3 regardless of the difference in size and mark price
  ======> fundingFeePerUnit:  -30419422517522

  //@audit => Same fundingFeePerUnit as the account1 in Market5 regardless of the difference in size and mark price
  Values while liquidating in Market ID:  5
  ======> fundingFeePerUnit:  -26240866280127   
  ===============================================
  ============ End of PoC Output ===============
  ===============================================

The funding fee of the liquidated accounts starting from the 2nd one will be computed wrong because the fundingFeePerUnit that will be used is not the actual value for each position, instead, all the liquidations will use the fundingFeePerUnit that was computed for the first liquidated position.

## Proof of Concept

I coded a PoC to demonstrate the problem about all accounts been liquidated using the same fundingFeePerUnit.

We'll need to add a couple of console.log statements to the TradingAccount.sol and LiquidationBranch.sol files, so we can see the exact values when the functions are called.

First, help me to add the next lines on the TradingAccount.sol file:
```solidity
import { console2 } from "forge-std/Test.sol";

library TradingAccount {

  ...

  function getAccountUnrealizedPnlUsd(Data storage self) internal view returns (SD59x18 totalUnrealizedPnlUsdX18) {
      uint256 cachedActiveMarketsIdsLength = self.activeMarketsIds.length();

      for (uint256 i; i < cachedActiveMarketsIdsLength; i++) {
         ...

          SD59x18 fundingFeePerUnitX18 = perpMarket.getNextFundingFeePerUnit(fundingRateX18, markPriceX18);
console2.log("Data of MarketID: ", marketId);
console2.log("======> fundingFeePerUnitX18: ", fundingFeePerUnitX18.intoInt256());

         ...
      }
  }

  ...

  function getAccountMarginRequirementUsdAndUnrealizedPnlUsd(
        Data storage self,
        uint128 targetMarketId,
        SD59x18 sizeDeltaX18
    )
        ...
    {
        ...

        for (uint256 i; i < cachedActiveMarketsIdsLength; i++) {
            ...

            // get funding fee per unit
            SD59x18 fundingFeePerUnit =
                perpMarket.getNextFundingFeePerUnit(perpMarket.getCurrentFundingRate(), markPrice);
console2.log("Values while liquidating in Market ID: ", perpMarket.id);
console2.log("======> fundingFeePerUnit: ", fundingFeePerUnit.intoInt256());

            ...
        }
    }

}
```

Now, help me to add the next lines on the LiquidationBranch.sol file:
```solidity
import { console2 } from "forge-std/Test.sol";

contract LiquidationBranch {

  ...

  function liquidateAccounts(uint128[] calldata accountsIds) external {
      ...
      for (uint256 i; i < accountsIds.length; i++) {
        console2.log("===============================================");
        // store current accountId being liquidated in working data
        ctx.tradingAccountId = accountsIds[i];
console2.log("  Liquidation data of account: ", ctx.tradingAccountId);

        ...
        ...
        ...
      }
    }

  ...
}
```

Finally, let's add the below PoC to the liquidateAccounts.t.sol test file:

```solidity
// Make sure to add the console2 log dependency at the very top
import { console2 } from "forge-std/Test.sol";

contract LiquidateAccountsIntegrationTest is Base_Test {
  ...

  //PoC
  function test_sameFundingFeeForOperationOnSameBlockTimestampPoC()
      external
      givenTheSenderIsARegisteredLiquidator
      whenTheAccountsIdsArrayIsNotEmpty
      givenAllAccountsExist
  {
      uint256 marketId = 3;
      uint256 secondMarketId = 5;
      bool isLong = true;
      uint256 timeDelta = 1 weeks;

      TestFuzzGivenThereAreLiquidatableAccountsInTheArrayContext memory ctx;

      ctx.fuzzMarketConfig = getFuzzMarketConfig(marketId);
      ctx.secondMarketConfig = getFuzzMarketConfig(secondMarketId);

      vm.assume(ctx.fuzzMarketConfig.marketId != ctx.secondMarketConfig.marketId);

      uint256 amountOfTradingAccounts = 2;

      ctx.marginValueUsd = 10_000e18 / amountOfTradingAccounts;
      ctx.initialMarginRate = ctx.fuzzMarketConfig.imr;

      deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd });

      // last account id == 0
      ctx.accountsIds = new uint128[](amountOfTradingAccounts);

      ctx.accountMarginValueUsd = ctx.marginValueUsd / (amountOfTradingAccounts + 1);

      //@audit => Open two positions on two different markets for Account1
      {
          ctx.tradingAccountId = createAccountAndDeposit(ctx.accountMarginValueUsd, address(usdz));

          openPosition(
              ctx.fuzzMarketConfig,
              ctx.tradingAccountId,
              ctx.initialMarginRate,
              ctx.accountMarginValueUsd / 2,
              isLong
          );

          openPosition(
              ctx.secondMarketConfig,
              ctx.tradingAccountId,
              ctx.secondMarketConfig.imr,
              ctx.accountMarginValueUsd / 2,
              isLong
          );

          ctx.accountsIds[0] = ctx.tradingAccountId;

          deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd });
      }

      //@audit => Open two positions on two different markets for Account2
      //@audit => The size of these positions is twice as big as the size of the positions of the account1!
      {
          ctx.tradingAccountId = createAccountAndDeposit(ctx.accountMarginValueUsd * 2, address(usdz));

          openPosition(
              ctx.fuzzMarketConfig,
              ctx.tradingAccountId,
              ctx.initialMarginRate,
              ctx.accountMarginValueUsd,
              isLong
          );

          openPosition(
              ctx.secondMarketConfig,
              ctx.tradingAccountId,
              ctx.secondMarketConfig.imr,
              ctx.accountMarginValueUsd,
              isLong
          );

          ctx.accountsIds[1] = ctx.tradingAccountId;

          deal({ token: address(usdz), to: users.naruto.account, give: ctx.marginValueUsd});
      }

      setAccountsAsLiquidatable(ctx.fuzzMarketConfig, isLong);
      setAccountsAsLiquidatable(ctx.secondMarketConfig, isLong);

      changePrank({ msgSender: liquidationKeeper });

      skip(timeDelta);

      SD59x18 totalUnrealizedPnlUsdX18;

      console2.log("===============================================");
      console2.log("=========== Start of PoC Output ===============");
      console2.log("===============================================");

      //@audit => when getAccountTotalUnrealizedPnl() is called, the fundingFeePerUnit of each position will be shown on the console (Before liquidating)

      console2.log("          Data for Naruto user / Account 1");
      totalUnrealizedPnlUsdX18 = perpsEngine.getAccountTotalUnrealizedPnl(ctx.accountsIds[0]);
      //console2.log("totalUnrealizedPnlUsdX18: ", totalUnrealizedPnlUsdX18.intoInt256());

      console2.log("===============================================");
      console2.log("          Data for Sasuke user / Account 2");
      totalUnrealizedPnlUsdX18 = perpsEngine.getAccountTotalUnrealizedPnl(ctx.accountsIds[1]);
      //console2.log("totalUnrealizedPnlUsdX18: ", totalUnrealizedPnlUsdX18.intoInt256());

      console2.log("===============================================");
      //@audit => when liquidateAccounts() is called, the fundingFeePerUnit of each position will be shown on the console (during the liquidation)
      perpsEngine.liquidateAccounts(ctx.accountsIds);

      console2.log("===============================================");
      console2.log("============ End of PoC Output ===============");
      console2.log("===============================================");
  }

}
```

Run the Poc with the command forge test --match-test test_sameFundingFeeForOperationOnSameBlockTimestampPoC -vvv, and let's analyze the output:
As we can see, while the accounts are been liquidated, the fundingFeePerUnit of the two accounts is the same, regardless of the difference in the position size and the mark price.

  ===============================================
  =========== Start of PoC Output ===============
  ===============================================
  //@audit => Data before running the liquidation!
            Data for Naruto user / Account 1
  Data of MarketID:  3
  //@audit => fundingFeePerUnit of account1 on Market3 will be the same fundingFeePerUnit for all the liquidated accounts
  ======> fundingFeePerUnitX18:  -30419422517522

  Data of MarketID:  5
  //@audit => fundingFeePerUnit of account1 on Market5 will be the same fundingFeePerUnit for all the liquidated accounts
  ======> fundingFeePerUnitX18:  -26240866280127
  ===============================================
            Data for Sasuke user / Account 2
  //@audit => This is the fundingFeePerUnit that should be used when liquidating account2, but instead, it will use the fundingFeePerUnit of account1

  Data of MarketID:  3
  ======> fundingFeePerUnitX18:  -30419400850761

  Data of MarketID:  5
  ======> fundingFeePerUnitX18:  -26240866002832
  ===============================================
  ===============================================
  //@audit => Data while liquidating the accounts
    Liquidation data of account:  1
  Values while liquidating in Market ID:  3
  ======> fundingFeePerUnit:  -30419422517522

  Values while liquidating in Market ID:  5
  ======> fundingFeePerUnit:  -26240866280127
  ===============================================
    Liquidation data of account:  2
  Values while liquidating in Market ID:  3
  //@audit => Same fundingFeePerUnit as the account1 in Market3 regardless of the difference in size and mark price
  ======> fundingFeePerUnit:  -30419422517522

  //@audit => Same fundingFeePerUnit as the account1 in Market5 regardless of the difference in size and mark price
  Values while liquidating in Market ID:  5
  ======> fundingFeePerUnit:  -26240866280127   
  ===============================================
  ============ End of PoC Output ===============
  ===============================================

## Recommendation

I'd recommend adding a conditional on the PerpetualMarket.getProportionalElapsedSinceLastFunding() function to handle the case when the elapsed time is 0, and instead of returning 0, return a fixed constant that would allow the computation of pendingFundingFeePerUnit and currentFundingRate.

The idea is to have a mechanism that can allow to execute multiple operations on the same block.timestamp without that causing problems when computing values dependent on the elapsed time.

```solidity
function getProportionalElapsedSinceLastFunding(Data storage self) internal view returns (UD60x18) {
if (block.timestamp == self.lastFundingTime) {
return a fixed value to allow the computation of pendingFundingFee and currentFundingRate.
}

    //@audit-ok => If lastFundingTime is != block.timestamp, this formula works fine!
    return ud60x18Convert(block.timestamp - self.lastFundingTime).div(
        ud60x18Convert(Constants.PROPORTIONALFUNDINGPERIOD)
    );
}
```

Low Risk Findings

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error that occurs during batch liquidation of perpetual positions when several accounts are liquidated in the same transaction. The contract computes a fundingFeePerUnit for each position based on the elapsed time since the last funding update, the average funding rate and the current mark price. Because the liquidation loop runs within a single block, block.timestamp is identical for all accounts, causing the function getProportionalElapsedSinceLastFunding to return zero for every account after the first. Consequently the pendingFundingFeePerUnit becomes zero and the currentFundingRate collapses to the lastFundingRate, so the nextFundingFeePerUnit for the second and subsequent positions is equal to the value calculated for the first position. This logic flaw means that positions with different sizes or mark prices are charged the same funding fee, leading to an incorrect accrued funding amount that is added to unrealized PnL. The impact is that liquidated traders receive a PnL that is either higher or lower than the protocol’s economic model predicts, effectively causing funds to disappear or be over‑charged. The bug manifests only when multiple accounts are liquidated in the same block, a scenario that is common for liquidators who batch calls to reduce gas costs. Users, liquidators and the protocol itself are affected because the accounting invariants that guarantee fair funding distribution are broken. The issue was discovered during a manual audit and reproduced with a proof‑of‑concept test that logged fundingFeePerUnit values before and during liquidation, showing identical values for different positions. It is hard to notice because the funding fee is a small component of the overall PnL and the discrepancy may be masked by market volatility, making the error appear as normal loss. The vulnerability belongs to the class of time‑dependent accounting bugs where a zero‑time delta leads to division‑by‑zero or nullified terms, similar to rounding or stale‑state errors. From a user perspective the expectation is that each liquidated position is charged a fee proportional to its size and market price, but the reality is that the fee is constant, causing unexpected zero or negative balances after liquidation. To remediate, the funding‑rate calculation must handle the case where elapsed time is zero by either using a non‑zero fallback constant or by deferring the funding update until after all positions have been processed, ensuring each position’s fundingFeePerUnit is computed with its own correct mark price and size. This restores the intended accounting guarantees and prevents incorrect fee application during batch liquidations.
