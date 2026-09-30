---
id: 20766
severity: "High"
---

# Incorrect math means `data.removeAndRepayData.removeAssetFromSGL` will never work once SGL has accrued interest

## Description

The code to remove shares from Singularity is as follows:

```solidity
singularity_.removeAsset(data.user, removeAssetTo, share);
```

Where `share` is computed in this way:

```solidity
uint256 share = yieldBox_.toShare(_assetId, _removeAmount, false);
```

The line is calculating: The (incorrectly rounded down) amount of shares of Yieldbox to burn in order to withdraw from Yieldbox the `_removeAmount`.

But the code is calling:

`singularity_.removeAsset(data.user, removeAssetTo, share);`

This is asking Singularity to remove a % (part) of the total assets in Singularity. Due to this, the line will stop working as soon as singularity has had any operation that generated interest.

## Proof of Concept

Please see the formula used by Singularity for pricing asset:

```solidity
function _removeAsset(address from, address to, uint256 fraction) internal returns (uint256 share) {
    if (totalAsset.base == 0) {
        return 0;
    }
    Rebase memory _totalAsset = totalAsset;
    uint256 allShare = _totalAsset.elastic + yieldBox.toShare(assetId, totalBorrow.elastic, false);
    share = (fraction * allShare) / _totalAsset.base;
}
```

As you can see, the `fraction` will be computed against `_totalAsset.elastic + yieldBox.toShare(assetId, totalBorrow.elastic, false);`. Meaning that the math will be incorrect as soon as any operation is done in Singularity.

This Poc is built on the public repo: <https://github.com/GalloDaSballo/yieldbox-foundry>

We show how a change in interest will change `fraction`. In my local testing, `fraction` and `shares` are already out of sync. However, due to decimals it may be possible for them to be the same value, until some interest will make `borrowElastic` grow.

## Recommendation

The unused function `getFractionForAmount` should help, minus some possible rounding considerations.

PR [here](https://github.com/Tapioca-DAO/tapioca-periph/commit/a22fdf0efe5a63538e072f4947ed65fd72e029a2).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect mathematical conversion used when a user attempts to remove assets from the Singularity (SGL) module. The contract computes a share value by converting the desired withdrawal amount to YieldBox shares with a rounding‑down operation, then passes that share directly to Singularity’s removeAsset function, which expects a fraction of the total assets rather than a raw share count. Because the fraction is calculated against the sum of the current elastic balance and the shares representing borrowed interest, any accrued interest changes the denominator, causing the share value to be too low. As a result, once Singularity has generated any interest, the removeAsset call no longer removes the intended amount; it may remove nothing or an amount far smaller than requested. This occurs under the condition that the protocol has performed any operation that adds interest to the total borrow elastic, which modifies the internal accounting used for the fraction calculation. Users attempting to withdraw after interest accrual experience a mismatch between the amount they expect and the amount actually transferred, often seeing a zero or unexpectedly reduced balance while the transaction reports success. The issue was discovered during a Code4rena audit by analysing the _removeAsset internal logic and testing scenarios where interest accrues, revealing that the fraction and share values diverge after a few interest‑generating operations. The bug is subtle because initial withdrawals may appear correct due to rounding coincidences, making it hard to notice until interest accumulates. It belongs to the class of accounting or rounding bugs where a value representing a proportion is incorrectly derived from a discrete token count, violating the protocol’s financial invariants and breaking the guarantee that users can retrieve their deposited assets. To remediate, the contract should compute the correct fraction using the dedicated getFractionForAmount helper (or an equivalent precise conversion) and ensure that the value passed to removeAsset matches the expected unit, handling rounding edge cases appropriately. This fix restores the alignment between requested withdrawal amounts and the internal accounting, allowing users to reliably withdraw their funds after interest accrues.
