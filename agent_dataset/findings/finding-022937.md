---
id: 22937
severity: "High"
---

# The manager can steal the rewards from all

## Description

When a Vault deposits liquidity into a Velodrome Concentrated Liquidity Pool (CLPool), it also has the option to stake that liquidity into a Velodrome Gauge, which will give rewards in the VELO token. However, the manager can directly call getReward while the VELO token is not supported in the Vault to steal those rewards from the Vault's users. Whenever the Vault has some liquidity staked into a Velodrome Gauge, the rewards generated from that staking are accounted towards the total Vault's value, which is accounted in VelodromeCLAssetGuard: s/guards/assetGuards/velodrome/VelodromeCLAssetGuard.sol#L129-L134
```solidity
if (isStaked) {
    //during increasing/decreasing staked liquidity the rewards move from earned to rewards
    address rewardToken = clGauge.rewardToken();
    tokenBalance = tokenBalance.add(_assetValue(pool, rewardToken, clGauge.earned(pool, tokenId)));
    tokenBalance = tokenBalance.add(_assetValue(pool, rewardToken, clGauge.rewards(tokenId)));
}
```
These rewards are accounted towards the total Vault's value even if the VELO token is supported or not. However, the manager uses the Vault to call CLGauge::getReward while the VELO token is not supported so those tokens are transferred to the Vault but are not accounted for the total value because that token is not supported. The function totalFundValueMutable, which is in charge of getting the total Vaul'ts value, will only loop over the supported assets:
```solidity
function totalFundValueMutable() external override returns (uint256 total) {
    uint256 assetCount = supportedAssets.length;
    for (uint256 i; i < assetCount; ++i) {
        address asset = supportedAssets[i].asset;
        address guard = IHasGuardInfo(factory).getAssetGuard(asset);
        uint256 balance;
        (bool hasFunction, bytes memory answer) = guard.call(abi.encodeWithSignature("isStateMutatingGuard()"));
        if (hasFunction && abi.decode(answer, (bool))) {
            balance = IMutableBalanceAssetGuard(guard).getBalanceMutable(poolLogic, asset);
        } else {
            balance = IAssetGuard(guard).getBalance(poolLogic, asset);
        }
        total = total.add(assetValue(asset, balance));
    }
}
```
Because of this, the unclaimed rewards from a Velodrome Gauge will be counted towards the Vault's total value, but if the manager disables the VELO token and claims the rewards, those tokens will be removed from the total value. This means that the users will experience a drop in the Vault's share price because the rewards are removed from the total assets. After the rewards are maliciously claimed by the manager, he could steal most of them by swapping the VELO tokens on 1Inch allowing 100% slippage, and sandwiching that transaction to extract the value. Usually, if a manager wants the Vault to perform a swap using 1Inch, some checks ensure that the slippage cannot be high to protect the user's funds. This is checked at SlippageAccumulator::updateSlippageImpact: s/utils/SlippageAccumulator.sol#L89
```solidity
function updateSlippageImpact(SwapData calldata swapData) external onlyContractGuard(swapData.to) {
    if (IHasSupportedAsset(swapData.poolManagerLogic).isSupportedAsset(swapData.srcAsset)) {
    }
}
```
However, as the code snippet is showing, the slippage of a swap won't be checked if the token being swapped is not supported by the Vault. Using this, a manager can trade all the untracked VELO allowing all the slippage, and can sandwich that transaction by extracting the maximum value out of that swap. will call _getReward internally. The manager can steal all VELO rewards from all Velodrome Gauges.

## Proof of Concept

no poc

## Recommendation

To mitigate this issue is recommended to check if the reward token is supported by the Vault before letting the manager call the functions getReward and withdraw.
```solidity
} else if (method == IVelodromeCLGauge.withdraw.selector) {
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    address rewardToken = velodromeCLGauge.rewardToken();
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(rewardToken), "unsupported asset: rewardToken");
    txType = uint16(TransactionType.VelodromeCLUnstake);
} else if (method == bytes4(keccak256("getReward(uint256)"))) {
    // it's possible to claim any reward token and sell it, we don't check if the reward token is supported
    uint256 tokenId = abi.decode(params, (uint256));
    _validateTokenId(nonfungiblePositionManagerGuard, tokenId, poolLogic);
    address rewardToken = velodromeCLGauge.rewardToken();
    require(IHasSupportedAsset(poolManagerLogic).isSupportedAsset(rewardToken), "unsupported asset: rewardToken");
    txType = uint16(TransactionType.Claim);
}
return (txType, false);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an asset‑tracking and reward‑claim bypass that allows the vault manager to steal VELO rewards generated by a Velodrome concentrated‑liquidity gauge. When the vault deposits liquidity into a Velodrome CLPool and stakes it in a gauge, the gauge’s earned and pending rewards are added to the vault’s total value by the VelodromeCLAssetGuard. This accounting is performed regardless of whether the reward token (VELO) is listed among the vault’s supported assets. The totalFundValueMutable function iterates only over supported assets, so any balance of an unsupported token is omitted from the reported total. Consequently, the vault’s share price reflects the expected reward value even though the actual token balance is not tracked. A manager who can invoke arbitrary vault calls can call the gauge’s getReward function while the VELO token remains unsupported. The call transfers the accumulated VELO tokens into the vault, but because VELO is not a supported asset, the tokens are not included in the total value calculation, effectively creating a hidden surplus. The manager can then disable VELO support, claim the hidden tokens, and swap them on 1Inch with no slippage protection – the SlippageAccumulator only checks slippage for supported assets, so an unsupported token can be traded with 100 % slippage. By sandwiching the swap the manager can extract the full market value of the stolen rewards. Users experience a sudden drop in the vault’s share price because the previously accounted rewards disappear from the total asset pool, leading to loss of value and potentially complete theft of the rewards. The issue occurs whenever the vault has liquidity staked in a Velodrome gauge, the reward token is not in the supported‑asset list, and the manager has permission to call getReward or withdraw. It affects all depositors in the vault, the protocol’s economic integrity, and any parties relying on accurate accounting. The flaw was discovered during a security audit that examined the asset‑guard logic and the slippage‑accumulator checks, noting that reward accounting and slippage validation are decoupled from the supported‑asset list. The problem is subtle because the vault’s accounting shows the expected reward value, yet the underlying token balance is invisible, making the loss appear as a normal price fluctuation rather than an exploit. To remediate, the contract should enforce that any reward token being claimed or withdrawn is first verified as a supported asset, and the slippage‑checking logic should be applied to all tokens regardless of support status, ensuring that hidden rewards cannot be extracted without proper accounting and protection.
