---
id: 25124
severity: "Crit/High"
---

# Wrong accounting of locked RA when repurchasing DS+PA with RA

## Description



## Proof of Concept

## Vulnerability Detail

NOTE: Currently `PsmLib.sol` incorrectly uses `lockUnchecked()` for the amount of RA provided by the user. As discussed with sponsor it should be `lockFrom()` in order to account for the RA provided.

After initially locking the RA provided, part of this amount is used to provide liquidity to the AMM via `VaultLibrary.provideLiquidityWithFee()`

```solidity
function repurchase(
        State storage self,
        address buyer,
        uint256 amount,
        IDsFlashSwapCore flashSwapRouter,
        IUniswapV2Router02 ammRouter
    ) internal returns (uint256 dsId, uint256 received, uint256 feePrecentage, uint256 fee, uint256 exchangeRates) {
        DepegSwap storage ds;

        (dsId, received, feePrecentage, fee, exchangeRates, ds) = previewRepurchase(self, amount);

        // decrease PSM balance
        // we also include the fee here to separate the accumulated fee from the repurchase
        self.psm.balances.paBalance -= (received);
        self.psm.balances.dsBalance -= (received);

        // transfer user RA to the PSM/LV
        // @audit-issue shouldnt it be lock checked, deposit -> redeemWithDs -> repurchase - locked would be 0
        self.psm.balances.ra.lockUnchecked(amount, buyer);

        // transfer user attrubuted DS + PA
        // PA
        (, address pa) = self.info.underlyingAsset();
        IERC20(pa).safeTransfer(buyer, received);

        // DS
        IERC20(ds._address).transfer(buyer, received);

        // Provide liquidity
        VaultLibrary.provideLiquidityWithFee(self, fee, flashSwapRouter, ammRouter);
    }
```

`provideLiqudityWithFee` internally uses `__provideLiquidityWithRatio()` which calculates the amount of RA that should be used to mint CT+DS in order to be able to provide liquidity.

```solidity
function __provideLiquidityWithRatio(
        State storage self,
        uint256 amount,
        IDsFlashSwapCore flashSwapRouter,
        address ctAddress,
        IUniswapV2Router02 ammRouter
    ) internal returns (uint256 ra, uint256 ct) {
        uint256 dsId = self.globalAssetIdx;

        uint256 ctRatio = __getAmmCtPriceRatio(self, flashSwapRouter, dsId);

        (ra, ct) = MathHelper.calculateProvideLiquidityAmountBasedOnCtPrice(amount, ctRatio);

        __provideLiquidity(self, ra, ct, flashSwapRouter, ctAddress, ammRouter, dsId);
    }
```

`__provideLiquidity()` uses `PsmLibrary.unsafeIssueToLv()` to account the RA locked.

```solidity
function __provideLiquidity(
        State storage self,
        uint256 raAmount,
        uint256 ctAmount,
        IDsFlashSwapCore flashSwapRouter,
        address ctAddress,
        IUniswapV2Router02 ammRouter,
        uint256 dsId
    ) internal {
        // no need to provide liquidity if the amount is 0
        if (raAmount == 0 && ctAmount == 0) {
            return;
        }

        PsmLibrary.unsafeIssueToLv(self, ctAmount);

        __addLiquidityToAmmUnchecked(self, raAmount, ctAmount, self.info.redemptionAsset(), ctAddress, ammRouter);

        _addFlashSwapReserve(self, flashSwapRouter, self.ds[dsId], ctAmount);
    }
```

RA locked is incremented with the amount of CT tokens minted.

```solidity
function unsafeIssueToLv(State storage self, uint256 amount) internal {
        uint256 dsId = self.globalAssetIdx;

        DepegSwap storage ds = self.ds[dsId];

        self.psm.balances.ra.incLocked(amount);

        ds.issue(address(this), amount);
    }
```

Consider the following scenario: For simplicity the minted values in the example may not be accurate, but the idea is to show the wrong accounting of locked RA.

1. PSM has 1000 RA locked.
2. Alice repurchase 100 DS+PA with providing 100 RA and we have fee=5% making the fee = 5
3. PSM will have 1100 RA locked and ra.locked would be 1100 also.
5. In `__provideLiquidity()` let say 3 of those 5 RA are used to mint CT+DS.
6. `PsmLibrary.unsafeIssueToLv()` would add 3 RA to the locked amount, making the psm.balances.ra.locked = 1103 while the real balance would still be 1100.

## Impact

Wrong accounting of locked RA would lead to over-distribution of rewards for users + after time last users to redeem might not be able to redeem as there wont be enough RA in the contract due to previous over-distribution. This breaks a core functionality of the protocol and the likelihood of this happening is very high, making the overall severity High.

## Code Snippet

`PsmLib.repurchase()`: [https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/PsmLib.sol#L293](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/PsmLib.sol#L293>)

## Recommendation

Consider either not accounting for the fee used to mint CT+DS as it is already accounted or do not initially account for the fee when users provide RA.
