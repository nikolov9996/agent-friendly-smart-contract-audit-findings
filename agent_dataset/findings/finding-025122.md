---
id: 25122
severity: "Medium"
---

# Admin will not be able to upgrade the smart contracts, breaking core functionality and rendering the upgradeable contracts useless

## Description



## Proof of Concept

`FlashSwapRouter`

```solidity
contract RouterState is IDsFlashSwapUtility, IDsFlashSwapCore, OwnableUpgradeable, UUPSUpgradeable, IUniswapV2Callee {
    ...
    function initialize(address moduleCore, address _univ2Router) external initializer notDelegated {
        __Ownable_init(moduleCore);
        __UUPSUpgradeable_init();

        univ2Router = IUniswapV2Router02(_univ2Router);
    }
    ...
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner notDelegated {}
}
```

`AssetFactory`

```solidity
contract AssetFactory is IAssetFactory, OwnableUpgradeable, UUPSUpgradeable {
    ...
    function initialize(address moduleCore) external initializer notDelegated {
        __Ownable_init(moduleCore);
        __UUPSUpgradeable_init();
    }
    ...
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner notDelegated {}
}
```

## Impact

The `UUPSUpgradeable` contract is rendered useless, which means the `AssetFactory` and `FlashSwapRouter` contracts can not be upgraded. This leads to breaking major functionality as well as the possibility of stuck/lost funds.

## Recommendation

Remove the `notDelegated` modifiers.
