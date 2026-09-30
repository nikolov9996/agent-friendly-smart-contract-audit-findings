---
id: 19072
severity: "High"
---

# Incorrect liquidation reward computation causes excess liquidator rewards to be given

## Description

In `_liquidateUser()` for BigBang and Singularity, the liquidator reward is derived by `_getCallerReward()`. However, it is incorrectly computed using `userBorrowPart[user]`, which is the portion of borrowed amount that does not include the accumulated fees (interests).

```solidity
uint256 callerReward = _getCallerReward(
    //@audit - userBorrowPart[user] is incorrect as it does not include accumulated fees
    userBorrowPart[user],
    startTVLInAsset,
    maxTVLInAsset
);
```

Using only `userBorrowPart[user]` is inconsistent with liquidation calculation in [Market.sol#L423-L424](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/Market.sol#L423-L424), which is based on borrowed amount including accumulated fees.

```solidity
function _isSolvent(
    address user,
    uint256 _exchangeRate
) internal view returns (bool) {
    ...
    return
        yieldBox.toAmount(
            collateralId,
            collateralShare *
                (EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
                collateralizationRate,
            false
        ) >=
        //@audit - note that the collateralizion calculation is based on borrowed amount with fees (using totalBorrow.elastic)
        // Moved exchangeRate here instead of dividing the other side to preserve more precision
        (borrowPart * _totalBorrow.elastic * _exchangeRate) /
            _totalBorrow.base;
}
```

As the protocol uses a dynamic liquidation incentives mechanism (see below), the liquidator will be given more rewards than required if the liquidator reward is derived by borrowed amount without accumulated fees. That is because the dynamic liquidation incentives mechanism decreases the rewards as it reaches 100% LTV. So computing the liquidator rewards using a lower value (without fees) actually gives liquidator a higher portion of the rewards.

```solidity
function _getCallerReward(
    uint256 borrowed,
    uint256 startTVLInAsset,
    uint256 maxTVLInAsset
) internal view returns (uint256) {
    if (borrowed == 0) return 0;
    if (startTVLInAsset == 0) return 0;

    if (borrowed < startTVLInAsset) return 0;
    if (borrowed >= maxTVLInAsset) return minLiquidatorReward;

    uint256 rewardPercentage = ((borrowed - startTVLInAsset) *
        FEE_PRECISION) / (maxTVLInAsset - startTVLInAsset);

    int256 diff = int256(minLiquidatorReward) - int256(maxLiquidatorReward);
    int256 reward = (diff * int256(rewardPercentage)) /
        int256(FEE_PRECISION) +
        int256(maxLiquidatorReward);

    return uint256(reward);
}
```

## Proof of Concept

1. Add the following console.log to [BigBang.sol#L581](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/bigBang/BigBang.sol#L581)

```solidity
console.log("    callerReward (without fees) = \t %d (actual)", callerReward);

callerReward= _getCallerReward(
    //userBorrowPart[user],
    //@audit borrowed amount with fees
    (userBorrowPart[user] * totalBorrow.elastic) / totalBorrow.base, 
    startTVLInAsset,
    maxTVLInAsset
);
console.log("    callerReward (with fees)  = \t %d (expected)", callerReward);
```

2. Add and run the following test in `bigBang.test.ts`. The console.log will show that the expected liquidator reward is lower when computed using borrowed amount with fees.

```typescript
it.only('peakbolt - liquidation reward computation', async () => {
    const {
        wethBigBangMarket,
        weth,
        wethAssetId,
        yieldBox,
        deployer,
        eoa1,
        __wethUsdcPrice,
        __usd0WethPrice,
        multiSwapper,
        usd0WethOracle,
        timeTravel,
    } = await loadFixture(register);

    await weth.approve(yieldBox.address, ethers.constants.MaxUint256);
    await yieldBox.setApprovalForAll(wethBigBangMarket.address, true);

    await weth
        .connect(eoa1)
        .approve(yieldBox.address, ethers.constants.MaxUint256);
    await yieldBox
        .connect(eoa1)
        .setApprovalForAll(wethBigBangMarket.address, true);

    const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(
        10,
    );
    await weth.connect(eoa1).freeMint(wethMintVal);
    const valShare = await yieldBox.toShare(
        wethAssetId,
        wethMintVal,
        false,
    );
    await yieldBox
        .connect(eoa1)
        .depositAsset(
            wethAssetId,
            eoa1.address,
            eoa1.address,
            0,
            valShare,
        );

    console.log("wethMintVal = %d", wethMintVal);
    console.log("__wethUsdcPrice = %d", __wethUsdcPrice);

    console.log("--------------------- addCollateral ------------------------");
    
    await wethBigBangMarket
        .connect(eoa1)
        .addCollateral(eoa1.address, eoa1.address, false, 0, valShare);

    //borrow
    const usdoBorrowVal = wethMintVal
        .mul(74) 
        .div(100)
        .mul(__wethUsdcPrice.div((1e18).toString()));

    console.log("--------------------- borrow ------------------------");
    await wethBigBangMarket
        .connect(eoa1)
        .borrow(eoa1.address, eoa1.address, usdoBorrowVal);

    // Can't liquidate
    const swapData = new ethers.utils.AbiCoder().encode(
        ['uint256'],
        [1],
    );

    timeTravel(100 * 86400);

    console.log("--------------------- price drop ------------------------");

    const priceDrop = __usd0WethPrice.mul(15).div(10).div(100);
    await usd0WethOracle.set(__usd0WethPrice.add(priceDrop));

    await wethBigBangMarket.updateExchangeRate();

    const borrowPart = await wethBigBangMarket.userBorrowPart(
        eoa1.address,
    );

    console.log("--------------------- liquidate (success) ------------------------");

    await expect(
        wethBigBangMarket.liquidate(
            [eoa1.address],
            [borrowPart],
            multiSwapper.address,
            swapData,
        ),
    ).to.not.be.reverted;

    return; 
   
});
```

## Recommendation

Change [BigBang.sol#L576-L580](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/bigBang/BigBang.sol#L576-L580), [SGLLiquidation.sol#L310-L314](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/singularity/SGLLiquidation.sol#L310-L314), [Market.sol#L364](https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/markets/Market.sol#L364) from

```solidity
uint256 callerReward = _getCallerReward(
    userBorrowPart[user],
    startTVLInAsset,
    maxTVLInAsset
);
```

to

```solidity
uint256 callerReward = _getCallerReward(
    (userBorrowPart[user] * totalBorrow.elastic) / totalBorrow.base,
    startTVLInAsset,
    maxTVLInAsset
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract’s liquidation routine calculates the liquidator’s reward by calling _getCallerReward with the value userBorrowPart[user]. This value represents only the principal portion of the user’s debt and deliberately excludes any interest or fees that have accrued on the loan. The protocol’s solvency check and the dynamic liquidation incentive model, however, are based on the total borrowed amount that includes those accumulated fees (totalBorrow.elastic). Because the reward function is designed to reduce the liquidator’s percentage as the borrowed amount approaches the maximum allowed TVL, feeding it a smaller number (principal only) makes the computed reward percentage larger than intended. When a liquidation is triggered after interest has built up, the liquidator therefore receives a higher share of the collateral than the protocol’s economics prescribe. This over‑payment drains funds from the pool, unfairly benefits liquidators, and reduces the value available to lenders and other borrowers. The flaw manifests only during liquidation events where the debt has accrued fees; in a fresh loan with no interest the calculation appears correct, which makes the problem easy to miss during casual testing. It was discovered during a formal audit when the auditors compared the reward calculation against the borrowing logic and confirmed the discrepancy with console logs and a targeted unit test that showed the reward with fees was consistently lower. The issue belongs to the class of “incorrect accounting in incentive calculations” where a mismatch between the metric used for eligibility and the metric used for reward leads to systematic over‑payment. From a user’s perspective a liquidator may notice that they receive more tokens than expected, while borrowers may see their positions liquidated with a higher cost than the protocol documentation suggests. The business logic that assumes the reward scales with the true debt is violated, breaking the intended balance between risk mitigation and compensation. The recommended fix is to replace the call argument with the debt amount that includes accrued fees, for example by converting userBorrowPart[user] to the full borrowed amount using (userBorrowPart[user] * totalBorrow.elastic) / totalBorrow.base before passing it to _getCallerReward. This aligns the reward computation with the solvency check and restores the intended incentive curve.
