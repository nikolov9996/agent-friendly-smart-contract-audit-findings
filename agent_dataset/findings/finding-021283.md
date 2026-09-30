---
id: 21283
severity: "High"
---

# The previous milestone stem should be scaled for use with the new gauge point system which uses untruncated values moving forward

## Description

Within the Beanstalk Silo, the milestone stem for a given token is the cumulative amount of grown stalk per BDV for this token at the last `stalkEarnedPerSeason` update. Previously, the milestone stem was stored in its truncated representation; however, the seed gauge system now stores the value in its untruncated form due to the new granularity of grown stalk and the frequency with which these values are updated.

At the time of upgrade, the previous (truncated) milestone stem for each token should be scaled for use with the gauge point system by multiplying up by a factor of `1e6`. Otherwise, there will be a mismatch in decimals when [calculating the stem tip](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibTokenSilo.sol#L388-L391).

```solidity
_stemTipForToken = s.ss[token].milestoneStem +
    int96(s.ss[token].stalkEarnedPerSeason).mul(
        int96(s.season.current).sub(int96(s.ss[token].milestoneSeason))
    );
```

The mixing of decimals between the old milestone stem (truncated) and the new milestone stem (untruncated, after the first `gm` call following the BIP-39 upgrade) breaks the existing grown stalk accounting, resulting in a loss of grown stalk for depositors.

## Proof of Concept

The [previous implementation](https://github.com/BeanstalkFarms/Beanstalk/blob/7606673/protocol/contracts/libraries/Silo/LibTokenSilo.sol#L376-L391) returns the cumulative stalk per BDV with 4 decimals:
```solidity
    function stemTipForToken(address token)
        internal
        view
        returns (int96 _stemTipForToken)
    {
        AppStorage storage s = LibAppStorage.diamondStorage();

        // SafeCast unnecessary because all casted variables are types smaller that int96.
        _stemTipForToken = s.ss[token].milestoneStem +
        int96(s.ss[token].stalkEarnedPerSeason).mul(
            int96(s.season.current).sub(int96(s.ss[token].milestoneSeason))
        ).div(1e6); //round here
    }
```

Which can be mathematically abstracted to:
$$StemTip(token) = getMilestonStem(token) + (current \ season - getMilestonStemSeason(token)) \times \frac{stalkEarnedPerSeason(token)}{10^{6}}$$

This division by $10^{6}$ happens because the stem tip previously had just 4 decimals. This division allows backward compatibility by not considering the final 6 decimals. Therefore, the stem tip **MUST ALWAYS** have 4 decimals.

The milestone stem is now [updated in each `gm` call](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/LibGauge.sol#L265-L268) so long as all [LP price oracles pass their respective checks](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/LibGauge.sol#L65-L67). Notably, the milestone stem is now stored with 10 decimals (untruncated), hence why the second term of the abstraction has omitted the `10^{6}` division in `LibTokenSilo::stemTipForTokenUntruncated`.

However, if the existing milestone stem is not escalated by $10^{6}$ then the addition performed during the upgrade and in subsequent `gm` calls makes no sense. This is mandatory to be handled within the upgrade otherwise every part of the protocol which calls `LibTokenSilo.stemTipForToken` will receive an incorrect value, except for BEAN:ETH Well LP (given it was created after the Silo v3 upgrade).

Some instances where this function is used include:
* [`EnrootFacet::enrootDeposit`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/EnrootFacet.sol#L91)
* [`EnrootFacet::enrootDeposits`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/EnrootFacet.sol#L131)
* [`MetaFacet::uri`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/metadata/MetadataFacet.sol#L36)
* [`ConvertFacet::_withdrawTokens`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/ConvertFacet.sol#L129-148)
* [`LibSilo::__mow`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibSilo.sol#L382)
* [`LibSilo::_removeDepositFromAccount`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibSilo.sol#L545)
* [`LibSilo::_removeDepositsFromAccount`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibSilo.sol#L604)
* [`Silo::_plant`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/SiloFacet/Silo.sol#L110)
* [`TokenSilo::_deposit`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/SiloFacet/TokenSilo.sol#L173)
* [`TokenSilo::_transferDeposits`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/beanstalk/silo/SiloFacet/TokenSilo.sol#L367)
* [`LibLegacyTokenSilo::_mowAndMigrate`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibLegacyTokenSilo.sol#L306)
* [`LibTokenSilo::_mowAndMigrate`](https://github.com/BeanstalkFarms/Beanstalk/blob/dfb418d185cd93eef08168ccaffe9de86bc1f062/protocol/contracts/libraries/Silo/LibLegacyTokenSilo.sol#L306)

As can be observed, critical parts of the protocol are compromised, leading to further cascading issues.

## Recommendation

Scale up the existing milestone stem for each token:
```diff
for (uint i = 0; i < siloTokens.length; i++) {
+   s.ss[siloTokens[i]].milestoneStem = int96(s.ss[siloTokens[i]].milestoneStem.mul(1e6));
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a precision‑scaling mismatch introduced during the BIP‑39 upgrade of the Beanstalk Silo. Previously the milestone stem – the cumulative amount of grown stalk per BDV for each token – was stored in a truncated form with four decimal places. The new gauge point system records the same value in an untruncated form with ten decimal places, because stalk growth is now tracked with finer granularity and updated more frequently. The upgrade code failed to scale the existing truncated milestoneStem by the factor 1e6, so the old four‑decimal value was added directly to the new ten‑decimal value when calculating the stem tip. This mixing of units causes the stem tip formula to produce a value that is off by six decimal places, effectively discarding a large portion of the accrued stalk. As a result, depositors receive less grown stalk than they earned, and in some cases the accounting may show a zero or dramatically reduced reward balance. The issue manifests when the protocol calls LibTokenSilo.stemTipForToken or any function that relies on the stem tip, such as enrootDeposit, withdraw, metadata URI generation, and internal mowing logic. Users notice that their expected rewards disappear or are far lower than before the upgrade, while the UI may still display the deposited amount correctly, making the problem hard to spot. The bug was discovered by the Cyfrin audit team while reviewing the upgrade logic and noticing that the division by 1e6 present in the legacy code was no longer applied after the gauge point change. Because the mismatch is subtle – it involves hidden decimal scaling rather than an outright revert or revert‑like error – it can remain unnoticed until accounting discrepancies surface. The vulnerability belongs to the class of decimal‑precision or unit‑conversion bugs, where stored values are combined without proper scaling, violating the protocol’s accounting assumptions that stalk growth is additive and linear. To remediate, the upgrade must multiply each token’s existing milestoneStem by 1e6 before storing it, ensuring both the old and new values share the same ten‑decimal precision. After this correction, the stem tip calculation will correctly reflect the full amount of grown stalk, restoring accurate reward accounting for all affected tokens.
