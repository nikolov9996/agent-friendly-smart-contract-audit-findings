---
id: 25112
severity: "Crit/High"
---

# FlashSwapRouter::emptyReserve() and FlashSwapROuter::emptyReservePartial() functions return incorrect values

## Description



## Proof of Concept

[Gist](<https://gist.github.com/AtanasDimulski/3f9bfc84c63e1c977b877613b644c0e2>)

After following the steps in the above mentioned [gist](<https://gist.github.com/AtanasDimulski/3f9bfc84c63e1c977b877613b644c0e2>) add the following test to the `AuditorTests.t.sol` contract:

```solidity
    function test_IncorrectEmptyReserveReturnedValue() public {
        vm.startPrank(alice);
        WETH.mint(alice, 10e18);
        WETH.approve(address(moduleCore), type(uint256).max);
        moduleCore.depositLv(id, 10e18);
        Asset(lvAddress).approve(address(moduleCore), type(uint256).max);
        vm.expectRevert(bytes("TransferHelper::transferFrom: transferFrom failed"));
        moduleCore.redeemEarlyLv(id, alice, 10e18);
        vm.stopPrank();
    }
```

To run the test use: `forge test -vvv --mt test_IncorrectEmptyReserveReturnedValue`

## Impact

When it comes to [FlashSwapRouter::emptyReserve()](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/core/flash-swaps/FlashSwapRouter.sol#L69-L72>), instead of the excess DS in the LV being paired with CT to redeem RA, all of the CT returned from the liquidation of LP will be used to claim RA + PA in the PSM, this is contrary of what is expected from the function according to the docs, and the comments, and may result in [VaultLib::_liquidatedLp()](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/libraries/VaultLib.sol#L349-L393>) function claiming much more PA tokens than it should, and distributing them to LV holders. In the case of [FlashSwapROuter::emptyReservePartial()](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/core/flash-swaps/FlashSwapRouter.sol#L74-L82>), the last users to withdraw won't be able to do so. The last user that tries to redeem his LV tokens won't be able to do so, and he won't receive his RA tokens back, locking the RA tokens in the contract.

## Recommendation

A lot of things have to be considered when fixing this problems, simply returning the amount that was redeemed may introduce other problems. Returning the amount that was redeemed seems to be okay when it comes to the [FlashSwapRouter::emptyReserve()](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/core/flash-swaps/FlashSwapRouter.sol#L69-L72>) function.
