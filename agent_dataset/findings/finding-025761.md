---
id: 25761
severity: "Medium"
---

# ZivoeYDL::earningsTrancheuse() always assumes that daysBetweenDistributions have passed, which might not be the case

## Description



## Proof of Concept

## Vulnerability Detail

There is a yield target for senior and junior tranches over a [daysBetweenDistributions](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L459-L463>) period that when exceeded, sends the rewards to [residuals](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L469-L471>). However, the current code will not strictly follow the expected `APY` for senior tranches, as the earning of tranches are calculated based on `daysBetweenDistributions`, but `ZivoeYDL::distributeYield()` may be called significantly [after](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L215-L218>) the `daysBetweenDistributions` mark.

Add the following test to `Test_ZivoeYDL.sol` to confirm that when the senior tranche yield reached the expected target for `30` days, if the time that `ZivoeYDL::distributeYield()` was called increased, the yield distributed to the senior tranch remains the same.

```solidity
function test_POC_ZivoeYDL_distributeYield_notEnforcingTranchesPeriod() public {
    uint256 amtSenior = 1500 ether; // Minimum amount $1,000 USD for each coin.
    uint256 amount = 1000 ether;

    // Simulating the ITO will "unlock" the YDL
    simulateITO_byTranche_optionalStake(amtSenior, true);

    // uncomment this line instead to confirm that it's the same value below
    //hevm.warp(YDL.lastDistribution() + YDL.daysBetweenDistributions() * 86400);
    hevm.warp(YDL.lastDistribution() + YDL.daysBetweenDistributions() * 86400 + 1 days);

    // Deal DAI to the YDL
    mint("DAI", address(YDL), amount);

    YDL.distributeYield();

    console.log(IERC20(DAI).balanceOf(address(stSTT)));
}
```

## Impact

Guaranteed less `APY` for junior and senior tranches. The amount depends on how much time the call to `ZivoeYDL::distributeYield()` was delayed since `block.timestamp` reached `lastDistribution + daysBetweenDistributions * 86400`.

## Code Snippet

[distributeYield()](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L215-L218>)

```solidity
function distributeYield() external nonReentrant {
    ...
    require(
        block.timestamp >= lastDistribution + daysBetweenDistributions * 86400,
        "ZivoeYDL::distributeYield() block.timestamp < lastDistribution + daysBetweenDistributions * 86400"
    );
    ...
```

[ZivoeYDL::earningsTrancheuse()](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L459-L463>)

```solidity
function earningsTrancheuse(uint256 yP, uint256 yD) public view returns (
    uint256[] memory protocol, uint256 senior, uint256 junior, uint256[] memory residual
) {
    ...
    uint256 _seniorProportion = MATH.seniorProportion(
        IZivoeGlobals_YDL(GBL).standardize(yD, distributedAsset),
        MATH.yieldTarget(emaSTT, emaJTT, targetAPYBIPS, targetRatioBIPS, daysBetweenDistributions),
        emaSTT, emaJTT, targetAPYBIPS, targetRatioBIPS, daysBetweenDistributions
    );
    ...
}
```

## Recommendation

Modify the [ZivoeMath::seniorProportion()](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeMath.sol#L68-L75>) and [ZivoeMath::yieldTarget()](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeMath.sol#L121-L123>) implementations to use seconds instead of days for `T`. Then, in `Zivoe::YDL::earningsTrancheuse()`, instead of [daysBetweenDistributions](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L459-L463>) when calculating the yield target and senior proportion, use `block.timestamp - lastDistribution`. Also, in `ZivoeYDL::distributeYield()`, `lastDistribution = block.timestamp;` must be moved after [earningsTrancheuse()](<https://github.com/sherlock-audit/2024-03-zivoe/blob/main/zivoe-core-foundry/src/ZivoeYDL.sol#L227-L232>) is called.
