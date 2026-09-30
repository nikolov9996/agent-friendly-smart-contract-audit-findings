---
id: 19930
severity: "High"
---

# Rogue plugin can become unremovable and

## Description

StakingModule's plugin that turned rogue can deny any attempts of its removal and can effectively stop the contract, disturbing the whole range of StakingModule operations. I.e. if any plugin turns malicious due to bug or upgrade altering its functionality vs one that was in place as of the time of its addition to StakingModule, such malicious plugin can halt StakingModule and freeze all the funds staked. The reason is removePlugins() having require(IPlugin(plugin).deactivated()) condition, which success is required. Suppose that a plugin turned malicious (as a result of a bug or by owner's intent via upgrade), begin to permanently return false for the deactivated() call. And, for instance, it can simultaneously return 2**256-1 in claim() to overflow the sum and revert the IPlugin(plugin).requiresNotification() calls. As all StakingModule operations will be frozen and funds withdrawal be unavailable in this scenario it will be permanent freeze of funds for all the stakers. If a plugin turns rogue:
It can return 2**256-1 in claim() to overflow the sum:
```solidity
function _claim(address account, address to, bytes calldata auxData) private
returns (uint256) {
    // balance of `to` before claiming
    uint256 balBefore = IERC20Upgradeable(tel).balanceOf(to);
    // call claim on all plugins and count the total amount claimed
    uint256 total;
    bytes[] memory parsedAuxData = parseAuxData(auxData);
    for (uint256 i = 0; i < nPlugins; i++) {
        try IPlugin(plugins[i]).claim(account, to, parsedAuxData[i]) returns
        (uint256 xClaimed) {
            total += xClaimed;
        } catch {
            emit PluginClaimFailed(plugins[i]);
        }
    }
}
```
This will block slash(), claim(), fullClaimAndExit(), partialClaimAndExit() functions. Also, it can revert the IPlugin(plugin).requiresNotification() call:
```solidity
/// @dev Calls `notifyStakeChange` on all plugins that require it. This is done in case any given plugin needs to do some stuff when a user exits.
/// @param account Account that is exiting
function _notifyStakeChangeAllPlugins(address account, uint256 amountBefore,
uint256 amountAfter) private {
    // loop over all plugins
    for (uint256 i = 0; i < nPlugins; i++) {
        // only notify if the plugin requires
        if (IPlugin(plugins[i]).requiresNotification()) {
            try IPlugin(plugins[i]).notifyStakeChange(account, amountBefore,
            amountAfter) {}
            catch {
                emit StakeChangeNotificationFailed(plugins[i]);
            }
        }
    }
}
```
It will also block stake(), partialExit(), exit(), and migration claimAndExitFor(), stakeFor() functions. As all involve _notifyStakeChangeAllPlugins(), for example:
```solidity
function claimAndExitFor(address account, address to, bytes calldata
auxData) external onlyRole(MIGRATOR_ROLE) nonReentrant returns (uint256,
uint256) {
    return (_claim(account, to, auxData), _exit(account, to));
}
```
```solidity
function _exit(address account, address to) private returns (uint256) {
    uint256 stakedAmt = _stakes[account].latest();
    _partialExit(account, to, stakedAmt);
    return stakedAmt;
}

function _partialExit(address account, address to, uint256 exitAmount)
private checkpointProtection(account) {
    if (exitAmount == 0) {
        return;
    }
    uint256 stakedAmt = _stakes[account].latest();
    require(stakedAmt >= exitAmount, "StakingModule: Cannot exit more than is staked");
    // notify plugins
    _notifyStakeChangeAllPlugins(account, stakedAmt, stakedAmt - exitAmount);
}
```

## Proof of Concept

no poc

## Recommendation

Consider adding force option to removePlugin(), for example:
```solidity
/// @notice Removes a plugin
function removePlugin(uint256 index, bool force) external onlyRole(PLUGIN_EDITOR_ROLE) {
    address plugin = plugins[index];
    require(force || IPlugin(plugin).deactivated(),
    "StakingModule::removePlugin: Plugin is not deactivated");
    pluginsMapping[plugin] = false;
    plugins[index] = plugins[nPlugins - 1];
    pluginIndicies[plugins[index]] = index;
    plugins.pop();
    nPlugins--;
    emit PluginRemoved(plugin, nPlugins);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the plugin management design of the StakingModule contract. The module allows external plugins to be attached, but removal of a plugin is gated by a require check that the plugin reports itself as deactivated via IPlugin.deactivated(). If a plugin becomes malicious – for example after a buggy upgrade or because its owner deliberately changes its behaviour – it can permanently return false for deactivated() and also return the maximum uint256 value (2**256‑1) from its claim() function. The claim() return value is summed into a total without overflow protection, so the addition overflows and causes the surrounding transaction to revert. In addition, the module calls IPlugin.requiresNotification() and IPlugin.notifyStakeChange() for every plugin during staking, exiting and migration operations. A rogue plugin that always reverts these calls blocks the internal _notifyStakeChangeAllPlugins loop, which in turn prevents stake(), partialExit(), exit(), claim(), slash() and other core functions from completing. Because the removal function cannot bypass the deactivated() check, the malicious plugin cannot be removed, effectively freezing the entire StakingModule. All stakers see their balances locked, withdrawals become unavailable, and the protocol’s accounting logic is broken – users expect to be able to claim rewards or exit their position but receive no response or a transaction that reverts. The issue was discovered during a security audit that examined the plugin lifecycle and identified that the contract trusts plugin‑provided boolean flags without any fallback mechanism. It is difficult to notice in normal operation because the plugin interface appears benign and the failure only manifests when the plugin returns unexpected values, which may be indistinguishable from a temporary failure. The recommended mitigation is to add a force‑removal option that allows an authorized role to bypass the deactivated() requirement, or to redesign the plugin interface to include safe arithmetic checks and to ensure that a single misbehaving plugin cannot halt the entire module. In essence, the bug is a classic case of an untrusted external component being given too much control over core protocol flow, leading to a denial‑of‑service and permanent fund lockup.
