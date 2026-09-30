---
id: 13806
severity: "High"
---

# MembershipERC1155 proxy cannot be upgraded

## Description

MembershipERC1155 proxy cannot be upgraded due to incorrect execution flow.

When a DAO membership is created by MembershipFactory, it is deployed as a MembershipERC1155 proxy, and proxyAdmin is used.

MembershipFactory.sol#L72-L76:

```solidity
        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(
            membershipImplementation,
            address(proxyAdmin),
            abi.encodeWithSignature("initialize(string,string,string,address,address)", daoConfig.ensname, "OWP", baseURI, _msgSender(), daoConfig.currency)
        );
```

The deployed MembershipERC1155 proxy is expected to be upgraded by proxyAdmin by calling upgradeAndCall().

ProxyAdmin.sol#L38-L44:

```solidity
    function upgradeAndCall(
        ITransparentUpgradeableProxy proxy,
        address implementation,
        bytes memory data
    ) public payable virtual onlyOwner {
        proxy.upgradeToAndCall{value: msg.value}(implementation, data);
    }
```

The expected upgrade flow would be like:

upgradeAndCall()                            upgradeToAndCall()
admin --------------------> proxyAdmin --------------------> proxy

Unfortunately, this simply won't work.&#x20;

When a TransparentUpgradeableProxy instance is called, the call will be forwarded to _fallback() function, and only if the caller is the admin of the proxy, the proxy is upgraded.

TransparentUpgradeableProxy.sol#L95-L105:

```solidity
    function _fallback() internal virtual override {
        if (msg.sender == _proxyAdmin()) {
            if (msg.sig != ITransparentUpgradeableProxy.upgradeToAndCall.selector) {
                revert ProxyDeniedAdminAccess();
            } else {
                _dispatchUpgradeToAndCall();
            }
        } else {
            super._fallback();
        }
    }
```

TransparentUpgradeableProxy.sol#L88-L90:

```solidity
    function _proxyAdmin() internal view virtual returns (address) {
        return _admin;
    }
```

The problem is proxyAdmin is not the admin of the MembershipERC1155 proxy, as can be seen in the constructor of TransparentUpgradeableProxy, when a proxy instance is deployed, it creates an an associated ProxyAdmin instance (let's call it proxyAdmin2) to manage the proxy, so the admin of the MembershipERC1155 proxy is proxyAdmin2 instead of proxyAdmin.

TransparentUpgradeableProxy.sol#L79-L83:

```solidity
    constructor(address logic, address initialOwner, bytes memory data) payable ERC1967Proxy(logic, data) {
        _admin = address(new ProxyAdmin(initialOwner));
        // Set the storage value and emit an event for ERC-1967 compatibility
        ERC1967Utils.changeAdmin(_proxyAdmin());
    }
```

As a result, any call to upgrade a MembershipERC1155 proxy will not be process internally but forwarded to the implementation, and the call will revert.

Therefore, to make MembershipERC1155 proxy  actually be upgraded, the flow should be like:

upgradeAndCall()                             upgradeAndCall()                                upgradeToAndCall()
admin --------------------> proxyAdmin --------------------> proxyAdmin2 --------------------> proxy

However, we cannot make proxyAdmin call upgradeAndCall() in proxyAdmin2, nor can we  transfer proxyAdmin2 ownership to admin.

Please follow the steps to run PoC to verify:
Follow the instructions to add foundry to the project (You may need to change hardhat version to 2.17.2 in package.json);
Create a test file (.t.sol) containing below in /test directory;
Run forge test --mt testAudit_upgradeProxy.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.22;

import {Test} from "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "../contracts/dao/MembershipFactory.sol";
import "../contracts/dao/CurrencyManager.sol";
import "../contracts/dao/tokens/MembershipERC1155.sol";
import {DAOType, DAOConfig, DAOInputConfig, TierConfig} from "../contracts/dao/libraries/MembershipDAOStructs.sol";

contract Audit is Test {
    address admin = makeAddr("Admin");
    address owpWallet = makeAddr("owpWallet");

    ERC20 WETH = new MockERC20("Wrapped ETH", "WETH", 18);
    ERC20 WBTC = new MockERC20("Wrapped BTC", "WBTC", 8);
    ERC20 USDC = new MockERC20("USDC", "USDC", 6);

    MembershipFactory membershipFactory;
    CurrencyManager currencyManager;
    
    function setUp() public {
        vm.startPrank(admin);

        // Deploy CurrencyManager
        currencyManager = new CurrencyManager();
        currencyManager.addCurrency(address(WETH));
        currencyManager.addCurrency(address(WBTC));
        currencyManager.addCurrency(address(USDC));

        // Deploy MembershipERC1155
        MembershipERC1155 membershipERC1155Implementation = new MembershipERC1155();

        // Deploy MembershipFactory
        membershipFactory = new MembershipFactory(
            address(currencyManager), 
            owpWallet, 
            "https://baseuri.com/", 
            address(membershipERC1155Implementation)
        );

        vm.stopPrank();
    }

    function testAudit_upgradeProxy() public {
        // Create DAO
        address creator = makeAddr("Creator");
        DAOInputConfig memory daoInputConfig = DAOInputConfig({
            ensname: "SPONSORED DAO",
            daoType: DAOType.SPONSORED,
            currency: address(USDC),
            maxMembers: 127,
            noOfTiers: 7
        });

        vm.startPrank(creator);
        address daoMemebershipProxy = membershipFactory.createNewDAOMembership(
            daoInputConfig, 
            createTierConfigs(
                daoInputConfig.noOfTiers, 
                ERC20(daoInputConfig.currency).decimals()
            )
        );
        vm.stopPrank();

        // Deploy new MembershipERC1155 implementation
        MembershipERC1155v2 membershipERC1155v2Implementation = new MembershipERC1155v2();

        vm.startPrank(admin);
        membershipFactory.updateMembershipImplementation(address(membershipERC1155v2Implementation));
        ProxyAdmin proxyAdmin = membershipFactory.proxyAdmin();
        // Upgrade MembershipERC1155 will revert
        vm.expectRevert();
        proxyAdmin.upgradeAndCall(ITransparentUpgradeableProxy(daoMemebershipProxy), address(membershipERC1155v2Implementation), "");
        vm.stopPrank();
    }

    function createTierConfigs(uint noOfTiers, uint8 decimals) private returns (TierConfig[] memory tiers) {
        tiers = new TierConfig[](noOfTiers);

        uint price = 1 * 10 ** decimals;
        uint power = 1;
        for (int i = int(noOfTiers) - 1; i >= 0; --i) {
            uint index = uint(i);
            tiers[index] = TierConfig({
                amount: 2 ** index,
                price: price,
                power: power,
                minted: 0
            });

            price *= 2;
            power *= 2;
        }
    }
}

contract MockERC20 is ERC20 {
    uint8 _decimals;

    constructor(
        string memory name_, 
        string memory symbol_, 
        uint8 decimals_
    ) ERC20(name_, symbol_) {
        _decimals = decimals_;
    }

    function decimals() public view override returns (uint8) {
        return _decimals;
    }
}

contract MembershipERC1155v2 is MembershipERC1155 {}
```

MembershipERC1155 proxy cannot be upgraded.

## Proof of Concept

no poc

## Recommendation

There are 2 mitigations:
The simplest solution is to declare proxyAdmin as an address (EOA/Multisig) instead of an ProxyAdmin instance, then it can call proxyAdmin2 (the address can be accessed by reading  the proxy's ERC-1967 admin slot) to upgrade MembershipERC1155proxy.
Or we can override TransparentUpgradeableProxy's _proxyAdmin() in a child contract, and use the child contract to create DAO membership proxy.

```solidity
contract MembershipERC1155Proxy is TransparentUpgradeableProxy {
    constructor(
        address _logic, 
        address initialOwner, 
        bytes memory _data
    ) TransparentUpgradeableProxy(_logic, initialOwner, _data) {}

    function _proxyAdmin() internal view override returns (address) {
        return ProxyAdmin(super._proxyAdmin()).owner();
    }
}
```

MembershipFactory.sol#L72-L76:

diff
TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(
TransparentUpgradeableProxy proxy = new MembershipERC1155Proxy(
            membershipImplementation,
            address(proxyAdmin),
            abi.encodeWithSignature("initialize(string,string,string,address,address)", daoConfig.ensname, "OWP", baseURI, _msgSender(), daoConfig.currency)
        );

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a proxy‑admin misconfiguration that makes the MembershipERC1155 proxy permanently non‑upgradeable. When the MembershipFactory creates a new DAO membership it deploys a TransparentUpgradeableProxy and passes a ProxyAdmin instance (named proxyAdmin) as the admin address. However, the constructor of TransparentUpgradeableProxy internally creates its own ProxyAdmin contract (proxyAdmin2) and stores that address as the proxy’s admin according to the ERC‑1967 standard. Consequently, the admin stored in the proxy is not the proxyAdmin supplied by the factory but a newly created proxyAdmin2. The upgrade function in ProxyAdmin (upgradeAndCall) forwards the call to the proxy’s upgradeToAndCall only if the caller matches the proxy’s admin. Because the caller (proxyAdmin) does not equal proxyAdmin2, the fallback logic treats the call as a regular user call, forwards it to the implementation, and the implementation reverts. The result is that any attempt to upgrade the MembershipERC1155 proxy through the factory’s proxyAdmin fails with a revert, even though the proxy otherwise functions correctly for normal token operations. This bug was discovered during a security audit when the upgrade flow was exercised in a Foundry test and the transaction consistently reverted. It is hard to notice because the proxy deployment succeeds, the contract can be interacted with, and the admin mismatch only manifests when an upgrade is attempted. The impact is that the DAO cannot replace the membership logic, patch bugs, or add new features, effectively locking the contract into its initial implementation. Users may expect that a new version of the membership contract will be deployed and that their experience will improve, but they will see no change, leading to confusion. The affected parties are the DAO administrators, members who rely on future upgrades, and any auditors or developers assuming upgradeability. The issue belongs to the class of proxy admin misconfiguration bugs, a subtype of access‑control errors where the administrative address is incorrectly set at deployment time. To remediate, the factory must ensure that the address used as the admin of the proxy is the same entity that later calls upgradeAndCall. This can be achieved by deploying the proxy with a known externally owned account or multisig as the admin, by reading the ERC‑1967 admin slot and using that address for upgrades, or by overriding the internal _proxyAdmin function in a custom proxy contract so that it returns the desired admin (for example, the owner of the original ProxyAdmin). Implementing any of these mitigations restores the intended upgrade path and re‑enables future contract evolution.
