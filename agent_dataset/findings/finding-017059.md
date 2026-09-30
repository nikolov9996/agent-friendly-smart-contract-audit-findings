---
id: 17059
severity: "High"
---

# NFTFloorOracle’s asset and feeder structures can be corrupted

## Description

NFTFloorOracle’s `_addAsset()` and `_addFeeder()` truncate the `assets` and `feeders` arrays indices to 255, both using `uint8 index` field in the corresponding structures and performing `uint8(assets.length - 1)` truncation on the new element addition.

`2^8 - 1` looks to be too tight as an **all time** element count limit. It can be realistically surpassed in a couple years time, especially given multi-asset and multi-feeder nature of the protocol. This way this isn’t a theoretical unsafe truncation, but an accounting malfunction that is practically reachable given long enough system lifespan, without any additional requirements as asset/feeder turnaround is a going concern state of the system.

## Proof of Concept

`feederPositionMap` and `assetFeederMap` use `uint8` indices:

    struct FeederRegistrar {
        // if asset registered or not
        bool registered;
        // index in asset list
        uint8 index;
        // if asset paused,reject the price
        bool paused;
        // feeder -> PriceInformation
        mapping(address => PriceInformation) feederPrice;
    }
    
    struct FeederPosition {
        // if feeder registered or not
        bool registered;
        // index in feeder list
        uint8 index;
    }

        /// @dev feeder map
        // feeder address -> index in feeder list
        mapping(address => FeederPosition) private feederPositionMap;
    
        ...
    
        /// @dev Original raw value to aggregate with
        // the NFT contract address -> FeederRegistrar which contains price from each feeder
        mapping(address => FeederRegistrar) public assetFeederMap;

On entry removal both `assets` array length do not decrease:

        function _removeAsset(address _asset)
            internal
            onlyWhenAssetExisted(_asset)
        {
            uint8 assetIndex = assetFeederMap[_asset].index;
            delete assets[assetIndex];
            delete assetPriceMap[_asset];
            delete assetFeederMap[_asset];
            emit AssetRemoved(_asset);
        }

On the contrary, feeders array is being decreased:

        function _removeFeeder(address _feeder)
            internal
            onlyWhenFeederExisted(_feeder)
        {
            uint8 feederIndex = feederPositionMap[_feeder].index;
            if (feederIndex >= 0 && feeders[feederIndex] == _feeder) {
                feeders[feederIndex] = feeders[feeders.length - 1];
                feeders.pop();
            }
            delete feederPositionMap[_feeder];
            revokeRole(UPDATER_ROLE, _feeder);
            emit FeederRemoved(_feeder);
        }

I.e. `assets` array element is set to zero with `delete`, but not removed from the array.

This means that `assets` will only grow over time, and will eventually surpass `2^8 - 1 = 255`. That’s realistic given that assets here are NFTs, whose variety will increase over time.

Once this happen the truncation will start to corrupt the indices:

        function _addAsset(address _asset)
            internal
            onlyWhenAssetNotExisted(_asset)
        {
            assetFeederMap[_asset].registered = true;
            assets.push(_asset);
            assetFeederMap[_asset].index = uint8(assets.length - 1);
            emit AssetAdded(_asset);
        }

This can happen with `feeders` too, if the count merely surpass `255` with net additions:

        function _addFeeder(address _feeder)
            internal
            onlyWhenFeederNotExisted(_feeder)
        {
            feeders.push(_feeder);
            feederPositionMap[_feeder].index = uint8(feeders.length - 1);
            feederPositionMap[_feeder].registered = true;
            _setupRole(UPDATER_ROLE, _feeder);
            emit FeederAdded(_feeder);
        }

This will lead to `_removeAsset()` and `_removeFeeder()` clearing another assets/feeders as the `assetFeederMap[_asset].index` and `feederPositionMap[_feeder].index` become broken being truncated. It will permanently mess the structures.

## Recommendation

As a simplest measure consider increasing the limit to `2^32 - 1`:

```solidity
        function _addAsset(address _asset)
            internal
            onlyWhenAssetNotExisted(_asset)
        {
            assetFeederMap[_asset].registered = true;
            assets.push(_asset);
            assetFeederMap[_asset].index = uint32(assets.length - 1);
            emit AssetAdded(_asset);
        }

        function _addFeeder(address _feeder)
            internal
            onlyWhenFeederNotExisted(_feeder)
        {
            feeders.push(_feeder);
            feederPositionMap[_feeder].index = uint32(feeders.length - 1);
            feederPositionMap[_feeder].registered = true;
            _setupRole(UPDATER_ROLE, _feeder);
            emit FeederAdded(_feeder);
        }
```

```solidity
    struct FeederRegistrar {
        // if asset registered or not
        bool registered;
        // index in asset list
        uint32 index;
        // if asset paused,reject the price
        bool paused;
        // feeder -> PriceInformation
        mapping(address => PriceInformation) feederPrice;
    }
    
    struct FeederPosition {
        // if feeder registered or not
        bool registered;
        // index in feeder list
        uint32 index;
    }
```

Also, consider actually removing `assets` array element in `_removeAsset()` via the usual moving of the last element as it’s done in `_removeFeeder()`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The NFTFloorOracle contract uses two dynamic arrays – one for registered NFT asset contracts and another for price feeder contracts – together with mappings that store the position of each element inside the arrays. The position fields are defined as uint8, which can only represent values from 0 to 255. When a new asset or feeder is added, the contract records the index using a cast to uint8 (uint8(assets.length - 1) or uint8(feeders.length - 1)). At the same time, the contract never shrinks the assets array; removal of an asset only deletes the entry in place, leaving a zero‑filled slot while the array length stays unchanged. Over time, as the protocol supports many NFT collections and multiple price feeders, the length of the assets array (and potentially the feeders array) will exceed 255. Once the length passes this threshold, the cast to uint8 silently truncates the higher bits, causing the stored index to wrap around modulo 256. This integer truncation corrupts the mapping entries: the stored index no longer points to the correct element, and subsequent calls to _removeAsset() or _removeFeeder() use the wrong index to delete items. As a result, the contract may delete an unrelated asset or feeder, leave stale entries, or lose price information, breaking the accounting logic that aggregates floor prices for NFTs. Users who rely on the oracle for pricing see incorrect or missing price data, potentially receiving zero price reports or stale values, which violates the expected business rule that each registered asset always has an up‑to‑date floor price. The vulnerability manifests only after a prolonged system lifetime when the cumulative number of distinct assets or feeders exceeds the 8‑bit limit, a condition that is realistic given the growing diversity of NFT collections. It was discovered during a formal security audit (Code4rena) where the auditors inspected the add/remove logic and noted the mismatch between array growth and index size. The bug is subtle because the use of delete on the array element appears to remove the asset, yet the underlying array length does not shrink, making the overflow invisible until the index wraps. The issue belongs to the class of integer truncation/overflow leading to storage corruption and broken invariant maintenance. To remediate, the index fields should be widened to at least uint32 (or uint256) to accommodate long‑term growth, and asset removal should follow the same swap‑pop pattern used for feeders, ensuring the array length reflects the actual number of active entries and preventing index mismatches. This conceptual fix restores the invariant that each mapping entry correctly references a live array element and preserves the integrity of the price aggregation mechanism.
