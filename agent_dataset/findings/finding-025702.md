---
id: 25702
severity: "Medium"
---

# previewRedeem and redeem functions deviate from the ERC4626 specification

## Description



## Proof of Concept

## Vulnerability Detail

> **Important** The [contest page](<https://github.com/sherlock-audit/2023-06-tokemak-xiaoming9090/tree/main#q-is-the-codecontract-expected-to-comply-with-any-eips-are-there-specific-assumptions-around-adhering-to-those-eips-that-watsons-should-be-aware-of>) explicitly mentioned that the `LMPVault` must conform with the ERC4626. Thus, issues related to EIP compliance should be considered valid in the context of this audit.
>
> **Q: Is the code/contract expected to comply with any EIPs? Are there specific assumptions around adhering to those EIPs that Watsons should be aware of?**
>
> src/vault/LMPVault.sol should be 4626 compatible

Let the value returned by `previewRedeem` function be $asset_{preview}$ and the actual number of assets obtained from calling the `redeem` function be $asset_{actual}$.

The following specification of `previewRedeem` function is taken from [ERC4626 specification](<https://eips.ethereum.org/EIPS/eip-4626>):

> Allows an on-chain or off-chain user to simulate the effects of their redeemption at the current block, given current on-chain conditions.
>
> MUST return as close to and no more than the exact amount of assets that would be withdrawn in a `redeem` call in the same transaction. I.e. `redeem` should return the same or more `assets` as `previewRedeem` if called in the same transaction.

It mentioned that the `redeem` should return the same or more `assets` as `previewRedeem` if called in the same transaction, which means that it must always be $asset_{preview} \le asset_{actual}$.

However, it is possible that the `redeem` function might return fewer assets than the number of assets previewed by the `previewRedeem` ($asset_{preview} > asset_{actual}$), thus it does not conform to the specification.

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L422](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L422>)

```solidity
File: LMPVault.sol
422:     function redeem(
423:         uint256 shares,
424:         address receiver,
425:         address owner
426:     ) public virtual override nonReentrant noNavDecrease ensureNoNavOps returns (uint256 assets) {
427:         uint256 maxShares = maxRedeem(owner);
428:         if (shares > maxShares) {
429:             revert ERC4626ExceededMaxRedeem(owner, shares, maxShares);
430:         }
431:         uint256 possibleAssets = previewRedeem(shares); // @audit-info  round down, which is correct because user won't get too many
432:
433:         assets = _withdraw(possibleAssets, shares, receiver, owner);
434:     }
```

Note that the `previewRedeem` function performs its computation based on the cached `totalDebt` and `totalIdle`, which might not have been updated to reflect the actual on-chain market condition. Thus, these cached values might be higher than expected.

Assume that `totalIdle` is zero and all WETH has been invested in the destination vaults. Thus, `totalAssetsToPull` will be set to $asset_{preview}$.

If a DV is making a loss, users could only burn an amount proportional to their ownership of this vault. The code will go through all the DVs in the withdrawal queue (`withdrawalQueueLength`) in an attempt to withdraw as many assets as possible. However, it is possible that the `totalAssetsPulled` to be less than $asset_{preview}$.

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L448](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L448>)

```solidity
File: LMPVault.sol
448:     function _withdraw(
449:         uint256 assets,
450:         uint256 shares,
451:         address receiver,
452:         address owner
453:     ) internal virtual returns (uint256) {
454:         uint256 idle = totalIdle;
455:         WithdrawInfo memory info = WithdrawInfo({
456:             currentIdle: idle,
457:             assetsFromIdle: assets >= idle ? idle : assets,
458:             totalAssetsToPull: assets - (assets >= idle ? idle : assets),
459:             totalAssetsPulled: 0,
460:             idleIncrease: 0,
461:             debtDecrease: 0
462:         });
463:
464:         // If not enough funds in idle, then pull what we need from destinations
465:         if (info.totalAssetsToPull > 0) {
466:             uint256 totalVaultShares = totalSupply();
467:
468:             // Using pre-set withdrawalQueue for withdrawal order to help minimize user gas
469:             uint256 withdrawalQueueLength = withdrawalQueue.length;
470:             for (uint256 i = 0; i < withdrawalQueueLength; ++i) {
471:                 IDestinationVault destVault = IDestinationVault(withdrawalQueue[i]);
472:                 (uint256 sharesToBurn, uint256 totalDebtBurn) = _calcUserWithdrawSharesToBurn(
473:                     destVault,
474:                     shares,
475:                     info.totalAssetsToPull - Math.max(info.debtDecrease, info.totalAssetsPulled),
476:                     totalVaultShares
477:                 );
..SNIP..
508:         // At this point should have all the funds we need sitting in in the vault
509:         uint256 returnedAssets = info.assetsFromIdle + info.totalAssetsPulled;
```

## Impact

It was understood from the protocol team that they anticipate external parties to integrate directly with the LMPVault (e.g., vault shares as collateral). Thus, the LMPVault must be ERC4626 compliance. Otherwise, the caller (internal or external) of the `previewRedeem` function might receive incorrect information, leading to the wrong action being executed.

## Code Snippet

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L422](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L422>)

## Recommendation

Ensure that $asset_{preview} \le asset_{actual}$.

Alternatively, document that the `previewRedeem` and `redeem` functions deviate from the ERC4626 specification in the comments and/or documentation.
