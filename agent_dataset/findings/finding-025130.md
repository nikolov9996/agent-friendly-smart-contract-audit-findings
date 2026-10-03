---
id: 25130
severity: "Low/Info"
---

# FairLauncher::newFairLaunch() may be misconfigured

## Description

The gasOperator or feesCfg may not be set when users create a new fair launch, as they are not set in the constructor and FairLauncher::newFairLaunch() is permissionless, so users may snipe the creation of a new fair launch without fees or a gas operator.

Additionally, the gas operator may not be changed after the D1MemeToken is created, so if it is address(0), it will never be set. Users have no incentive to set the correct _minBoughtOle because the only beneficiary is the fee recipient. The recipient of the lps may burn all the liquidity and steal all funds from the Uniswap pool.

However, these recipients are whitelisted offchain and the ones that are not will not be displayed on the frontend. The end time of the presale is not validated, so users can wait too long (possibly forever) for the presale to end to recover their ETH or proceed with the launch.

UniswapV2 only accepts minting up to type(uint112).max tokens, but this number is not capped in the amount to lp, which would break the launch.

## Proof of Concept

No PoC provided.

## Recommendation

The protocol is going to place these checks in the offchain components to avoid these misconfigurations and not display such misconfigured launches.
