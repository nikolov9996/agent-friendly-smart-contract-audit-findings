---
id: 21656
severity: "High"
---

# Revert due to underflow error, leading to lock of the liquidated NFT

## Description

The `IsolateLogic.sol#executeIsolateAuction()` is triggered by liquidators to launch a new auction or just participate in an existing one for isolated lending. Each NFT token has a predefined auction duration `nftAssetData.auctionDuration`, the MAX duration is 7 days. In the period of (e.g.) 7 days, the `borrowAmount` will keep increasing due to the interest:

```solidity
File: GenericLogic.sol#calculateNftLoanLiquidatePrice()

279:     vars.borrowAmount = nftLoanData.scaledAmount.rayMul(vars.normalizedIndex);
```

If the liquidator is the first bidder, the bid price must be greater than borrowed debt and the liquidate price. Otherwise, the liquidator will just try to outbid the last bidder, by at least 1%.

At the end of `executeIsolateAuction()`, it will transfer the underlying asset from the liquidator to escrow and increase the value of `assetData.totalBidAmout` by the bid amount from the liquidator (Note: remember the last point).

```solidity
File: IsolateLogic.sol#executeIsolateAuction()

269:     VaultLogic.erc20TransferInBidAmount(debtAssetData, params.msgSender, vars.totalBidAmount);
```

After 7 days, the liquidator who wins the auction will invoke `IsolateLogic.sol#executeIsolateLiquidate()` to implement the liquidation. It will calculate the `borrowAmount` and check for any remaining or extra amount.

```solidity
File: IsolateLogic.sol#executeIsolateLiquidate()

427:       vars.borrowAmount = loanData.scaledAmount.rayMul(vars.normalizedIndex);
```

Then, because the bid is already in the pool, it will sub-call to `VaultLogic.sol#erc20TransferOutBidAmountToLiqudity()` to increase liquidity in the pool `assetData.availableLiquidity` and decrease the `assetData.totalBidAmout` value.

The issue is here, is about how much `totalBidAmout` has decreased. In the below code snap is passing `totalBorrowAmount` to `erc20TransferOutBidAmountToLiqudity()`:

```solidity
File: IsolateLogic.sol#executeIsolateLiquidate()

464:     VaultLogic.erc20TransferOutBidAmountToLiqudity(debtAssetData, vars.totalBorrowAmount);
```

The `vars.totalBorrowAmount` is just the value of `vars.borrowAmount` (in case of one NFT in the liquidation). As we mentioned above, the borrowed amount will keep increasing over time and it will exceed the saved value in `assetData.totalBidAmout` (check the above note). This will lead the transaction to revert:

```solidity
File: VaultLogic.sol

503:   function erc20TransferOutBidAmountToLiqudity(DataTypes.AssetData storage assetData, uint amount) internal {
504:     assetData.totalBidAmout -= amount;
505:     assetData.availableLiquidity += amount;
506:   }
```

There are multiple scenarios to reach this point (revert):

  * The auction ends with only one bidder (the first bidder wins it), so the rest of the time (until the auction ends) the borrowed amount will keep accumulating interest.
  * The auction ends, but the borrowed amount exceeds the winner’s bid price (due to accumulated interest).

The liquidator wins the auction but he can’t withdraw/unlock the NFT, due to an **Arithmetic over/underflow** and fails when reducing the `assetData.totalBidAmout` value in `erc20TransferOutBidAmountToLiqudity()`.

## Proof of Concept

Foundry PoC:

  1. Please copy the following POC in `TestIntIsolateLiquidate.t.sol`:

```solidity
function test_POC_Should_LiquidateWETH() public {
  TestCaseLocalVars memory testVars;

  // deposit
  prepareWETH(tsDepositor1);
  uint256[] memory tokenIds = prepareIsolateBAYC(tsBorrower1);

  // borrow
  prepareBorrow(tsBorrower1, address(tsBAYC), tokenIds, address(tsWETH));

  // make some interest
  advanceTimes(365 days);

  // drop down nft price
  actionSetNftPrice(address(tsBAYC), 5000);

  //?1- first bidder wins the auction
  // auction
  tsLiquidator1.approveERC20(address(tsWETH), type(uint256).max);

  uint256[] memory bidAmounts = new uint256[](tokenIds.length);

  for (uint256 i = 0; i < tokenIds.length; i++) {
    bidAmounts[i] = 20561005318463975387;
  }

  tsLiquidator1.isolateAuction(tsCommonPoolId, address(tsBAYC), tokenIds, address(tsWETH), bidAmounts);

  //?2- wait and accumulate interest until the borrowed amount exceeds the winner's bid price
  // end the auction
  advanceTimes(25 hours);

  uint256[] memory liquidateAmounts = new uint256[](tokenIds.length);

  //?3- call `isolateLiquidate()` should revert
  // liquidate
  vm.expectRevert(stdError.arithmeticError);
  tsLiquidator1.isolateLiquidate(tsCommonPoolId, address(tsBAYC), tokenIds, address(tsWETH), liquidateAmounts, false);
}
```

  2. Go to `TestUser.sol` and update this part:

```solidity
File: TestUser.sol

45:     _uid = uid_;
46:     _tokenIds = new uint256[](1); //<== from 3 to 1
47:     for (uint i = 0; i < 1; i++) {//<== from 3 to 1
48:       _tokenIds[i] = uid_ + i;
49:     }
50:   }
```

  3. Test result:

```
Running 1 test for test/integration/TestIntIsolateLiquidate.t.sol:TestIntIsolateLiquidate
[PASS] test_POC_Should_LiquidateWETH() (gas: 1144530)
Logs:
  borrowAmount is: 20561005318463975387
  =============
  to reduce the totalBidAmout: 20561005318463975387
  reduce by amount: 20567041544435426364

Test result: ok. 1 passed; 0 failed; finished in 30.08ms
```

## Recommendation

Just decrease `assetData.totalBidAmout` by `vars.totalBidAmount`:

```solidity
File: IsolateLogic.sol#executeIsolateLiquidate()

- 464:  VaultLogic.erc20TransferOutBidAmountToLiqudity(debtAssetData, vars.totalBorrowAmount);
+ 464: VaultLogic.erc20TransferOutBidAmountToLiqudity(debtAssetData, vars.totalBorrowAmount, vars.totalBidAmount);

File: VaultLogic.sol
- 503:   function erc20TransferOutBidAmountToLiqudity(DataTypes.AssetData storage assetData, uint amount) internal {
+ 503:   function erc20TransferOutBidAmountToLiqudity(DataTypes.AssetData storage assetData, uint amount, uint bidAmount) internal {
- 504:     assetData.totalBidAmout -= amount;
+ 504:     assetData.totalBidAmout -= bidAmount;
  505:     assetData.availableLiquidity += amount;
  506:   }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic underflow that occurs when the liquidation routine tries to decrease the stored total bid amount using the accumulated borrow amount instead of the actual bid amount. In the isolated NFT lending flow, a liquidator can start an auction for a collateral NFT and place a bid that is stored in assetData.totalBidAmout. Over the auction period (up to seven days) the outstanding loan balance grows because interest is continuously added to the scaled amount. When the auction ends and the winning liquidator calls executeIsolateLiquidate, the contract recomputes the current borrowAmount and then calls erc20TransferOutBidAmountToLiqudity with vars.totalBorrowAmount as the amount to subtract from assetData.totalBidAmout. If the accrued borrowAmount exceeds the original bid, the subtraction underflows, causing a revert (arithmetic error) and preventing the function from completing. As a result the NFT remains locked in the protocol, the liquidator cannot withdraw the collateral, and the pool’s liquidity accounting becomes inconsistent. The issue manifests only after time has passed and interest has accumulated, making it easy to miss during short‑term testing. It was discovered during a Code4rena audit and reproduced with a Foundry proof‑of‑concept that advances the blockchain time until the borrow amount overtakes the bid. The bug belongs to the class of accounting‑logic errors where a contract uses an outdated or wrong monetary variable for balance adjustments, leading to underflow/overflow and state lock‑up. From a user’s perspective the transaction simply reverts with an arithmetic error, the expected NFT transfer never happens, and the user sees no funds returned despite having won the auction. The protocol’s business logic that the winning bid must always cover the debt is violated because the code does not enforce this invariant at liquidation time. The recommended fix is to subtract the stored bid amount (vars.totalBidAmount) from assetData.totalBidAmout while still adding the actual borrowed amount to availableLiquidity, thereby preserving accounting consistency and preventing the underflow.
