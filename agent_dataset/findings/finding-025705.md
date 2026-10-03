---
id: 25705
severity: "Crit/High"
---

# Destination Vault rewards are not added to idleIncrease when info.totalAssetsPulled > info.totalAssetsToPull

## Description



## Proof of Concept

## Vulnerability Detail

In the `_withdraw` function, Destination Vault rewards will be first recorded in `info.IdleIncrease` by `info.idleIncrease += _baseAsset.balanceOf(address(this)) - assetPreBal - assetPulled;`.

But when `info.totalAssetsPulled > info.totalAssetsToPull`, `info.idleIncrease` is directly assigned as `info.totalAssetsPulled - info.totalAssetsToPull`, and `info.totalAssetsPulled` is `assetPulled` without considering Destination Vault rewards.

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L482-L497](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L482-L497>)

```solidity
                uint256 assetPreBal = _baseAsset.balanceOf(address(this));
                uint256 assetPulled = destVault.withdrawBaseAsset(sharesToBurn, address(this));

                // Destination Vault rewards will be transferred to us as part of burning out shares
                // Back into what that amount is and make sure it gets into idle
                info.idleIncrease += _baseAsset.balanceOf(address(this)) - assetPreBal - assetPulled;
                info.totalAssetsPulled += assetPulled;
                info.debtDecrease += totalDebtBurn;

                // It's possible we'll get back more assets than we anticipate from a swap
                // so if we do, throw it in idle and stop processing. You don't get more than we've calculated
                if (info.totalAssetsPulled > info.totalAssetsToPull) {
                    info.idleIncrease = info.totalAssetsPulled - info.totalAssetsToPull;
                    info.totalAssetsPulled = info.totalAssetsToPull;
                    break;
                }
```

For example,

```solidity
                    // preBal == 100 pulled == 10 reward == 5 toPull == 6
                    // idleIncrease = 115 - 100 - 10 == 5
                    // totalPulled(0) += assetPulled == 10 > toPull
                    // idleIncrease = totalPulled - toPull == 4 < reward
```

The final `info.idleIncrease` does not record the reward, and these assets are not ultimately recorded by the Vault.

## Impact

The final `info.idleIncrease` does not record the reward, and these assets are not ultimately recorded by the Vault.

Meanwhile, due to the `recover` function's inability to extract the `baseAsset`, this will result in no operations being able to handle these Destination Vault rewards, ultimately causing these assets to be frozen within the contract.

## Code Snippet

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L482-L497](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L482-L497>)

## Recommendation

`info.idleIncrease = info.totalAssetsPulled - info.totalAssetsToPull;` -> `info.idleIncrease += info.totalAssetsPulled - info.totalAssetsToPull;`
