---
id: 23390
severity: "High"
---

# Incomplete validation in OpNetVaultAutoDeploy allows invalid burner configuration for registering operators with auto vault deployments

## Description

OpNetVaultAutoDeploy._validateConfig() is missing burner address validation that could lead to deployment failures. The function fails to validate a configuration scenario where `isBurnerHook` is enabled with `burner` as `address(0)`. This validation gap allows administrators to set invalid configurations that pass validation but cause all subsequent vault deployments to fail during slasher initialization. The validation logic only checks if burner hooks are enabled without slashers, but fails to validate the case where slashers are enabled with burner hooks but the burner address is zero.

//OpNetVaultAutoDeployLogic
```solidity
function _validateConfig(
    IOpNetVaultAutoDeploy.AutoDeployConfig memory config
) public view {
    if (config.collateral == address(0)) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidCollateral();
    }
    if (config.epochDuration == 0) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidEpochDuration();
    }
    uint48 slashingWindow = IVotingPowerProvider(address(this)).getSlashingWindow();
    if (config.epochDuration < slashingWindow) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidEpochDuration();
    }
    if (!config.withSlasher && slashingWindow > 0) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidWithSlasher();
    }
    if (!config.withSlasher && config.isBurnerHook) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidBurnerHook();
    } //@audit missing checks on burner address
}
```

Initialization logic in Symbiotic core's BaseSlasher:

```solidity
//BaseSlasher
function _initialize(
    bytes calldata data
) internal override {
    (address vault_, bytes memory data_) = abi.decode(data, (address, bytes));
    if (!IRegistry(VAULT_FACTORY).isEntity(vault_)) {
        revert NotVault();
    }
    __ReentrancyGuard_init();
    vault = vault_;
    BaseParams memory baseParams = __initialize(vault_, data_);
    if (IVault(vault_).burner() == address(0) && baseParams.isBurnerHook) {
        revert NoBurner();
    } //@audit if no burner, vault deployment reverts
    isBurnerHook = baseParams.isBurnerHook;
}
```

Undetected misconfiguration example:

```solidity
AutoDeployConfig memory maliciousConfig = AutoDeployConfig({
    epochDuration: 1000,
    collateral: validToken,
    burner: address(0), // Zero address burner
    withSlasher: true, // Slasher enabled
    isBurnerHook: true // Hook enabled but no burner!
});
// @audit This passes validation incorrectly
deployer.setAutoDeployConfig(maliciousConfig);
```

Impact: All new operator registrations fail in auto‑deployment mode until configuration is fixed.

## Proof of Concept

Add the following tests to `OpNetVaultAutoDeploy.t.sol`:

```solidity
function test_SetAutoDeployConfig_InvalidBurnerAddress_WithSlasherAndBurnerHook() public {
    // @audit This configuration should fail validation but currently passes
    // Config with slasher enabled, burner hook enabled, but zero address burner
    IOpNetVaultAutoDeploy.AutoDeployConfig memory maliciousConfig =
        IOpNetVaultAutoDeploy.AutoDeployConfig({
            epochDuration: slashingWindow,
            collateral: validConfig.collateral,
            burner: address(0), // Zero address burner - THIS IS THE ISSUE
            withSlasher: true, // Slasher enabled
            isBurnerHook: true // Hook enabled but no valid burner!
        });
    // Currently this passes validation incorrectly - it should revert
    deployer.setAutoDeployConfig(maliciousConfig);
    // Verify the incorrect config was set
    IOpNetVaultAutoDeploy.AutoDeployConfig memory setConfig = deployer.getAutoDeployConfig();
    assertEq(setConfig.burner, address(0));
    assertTrue(setConfig.withSlasher);
    assertTrue(setConfig.isBurnerHook);
}
```

```solidity
function test_AutoDeployFailure_WithInvalidBurnerConfig() public {
    // Set up the incorrect configuration that passes validation but causes deployment failures
    IOpNetVaultAutoDeploy.AutoDeployConfig memory maliciousConfig =
        IOpNetVaultAutoDeploy.AutoDeployConfig({
            epochDuration: slashingWindow,
            collateral: validConfig.collateral,
            burner: address(0), // Zero address burner
            withSlasher: true, // Slasher enabled
            isBurnerHook: true // Hook enabled
        });
    // This should pass validation
    deployer.setAutoDeployConfig(maliciousConfig);
    // Enable auto deployment
    deployer.setAutoDeployStatus(true);
    // Now try to register an operator - this should fail during vault deployment
    // because BaseSlasher._initialize() will revert with NoBurner() when it finds
    // that burner is address(0) but isBurnerHook is true
    vm.startPrank(operator1);
    // @audit This registration should fail during auto-deployment due to slasher initialization
    vm.expectRevert();
    deployer.registerOperator();
    vm.stopPrank();
    // Verify no vault was deployed
    address deployedVault = deployer.getAutoDeployedVault(operator1);
    assertEq(deployedVault, address(0));
    // Verify operator has no vaults
    address[] memory vaults = deployer.getOperatorVaults(operator1);
    assertEq(vaults.length, 0);
}
```

## Recommendation

Recommended Mitigation: Consider adding following check to `_validateConfig`:

```solidity
function _validateConfig(
    IOpNetVaultAutoDeploy.AutoDeployConfig memory config
) public view {
    // ... existing validations ...
    // @audit validate burner address
    if (config.withSlasher && config.isBurnerHook && config.burner == address(0)) {
        revert IOpNetVaultAutoDeploy.OpNetVaultAutoDeploy_InvalidBurnerAddress();
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incomplete validation in the OpNetVaultAutoDeploy contract that permits an invalid burner configuration to be accepted during auto‑deployment setup. Specifically, the _validateConfig function checks collateral, epoch duration, slashing window compatibility and the relationship between the withSlasher flag and the burner hook flag, but it omits any verification of the burner address itself. When an administrator creates a configuration with withSlasher set to true, isBurnerHook set to true, and burner equal to the zero address, the validation routine mistakenly considers the configuration valid. Later, during vault creation, the BaseSlasher contract’s _initialize function reads the burner address from the newly instantiated vault. Because the burner is zero while the burner hook flag is true, the function reverts with the NoBurner error. This revert aborts the entire vault deployment, causing the registerOperator call to fail and leaving the operator without a vault. The impact is a denial‑of‑service for all operators attempting to register in auto‑deployment mode: users see no vault address, their registration transactions revert, and any funds they intended to lock remain unspent, creating confusion and a perception that the protocol is broken. The issue occurs only when the specific combination of flags (withSlasher and isBurnerHook) is enabled and the burner address is not provided, a scenario that can be set by any privileged account that manages the auto‑deploy configuration. It affects protocol administrators, operators, and end‑users who rely on automatic vault provisioning. The flaw was discovered through manual code review during a security audit, where the reviewer noted the missing burner address check despite the later reliance on a non‑zero burner. The bug is subtle because the configuration appears syntactically correct and passes all existing checks, so the failure only surfaces at deployment time, making it hard to detect without thorough testing. To remediate, the validation function should be extended to reject configurations where withSlasher and isBurnerHook are true while burner equals address(0), thereby enforcing the protocol’s accounting assumption that a valid burner contract must exist whenever a burner hook is enabled. Adding this check prevents the NoBurner revert, restores reliable vault deployment, and eliminates the denial‑of‑service condition.
