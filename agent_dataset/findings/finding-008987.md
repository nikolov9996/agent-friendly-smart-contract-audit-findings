---
id: 8987
severity: "High"
---

# Incorrect proxy address tracking misconfigures USDXL pool tokens

## Description

The DeployUsdxlUtils._getUsdxlATokenProxy() and DeployUsdxlUtils._getUsdxlVariableDebtTokenProxy() functions incorrectly return implementation contract addresses instead of proxy addresses.
//File: src/deployments/utils/DeployUsdxlUtils.sol
```solidity
function _getUsdxlATokenProxy() internal view returns (address) {
    return address(usdxlAToken); // Returns implementation instead of proxy
}
function _getUsdxlVariableDebtTokenProxy() internal view returns (address) {
    return address(usdxlVariableDebtToken); // Returns implementation instead of proxy
}
```
This causes four main issues:
1. Incorrect contract exports in deployment artifacts in the _initializeUsdxlReserve() function.
2. Incorrect token configurations in the _setUsdxlAddresses() function, leaving the USDXL pool's AToken and VariableDebtToken unconfigured.
3. Incorrect facilitator configurations for the USDXL token in the _addUsdxlATokenAsEntity() function.
4. Incorrect discount token and strategy configurations in the _setDiscountTokenAndStrategy() function.

## Proof of Concept

No poc.

## Recommendation

Track the actual proxy addresses that are configured in the USDXL pool instead of using implementation addresses. This ensures that token configurations are applied to the correct contract instances that the pool interacts with.
To implement this:
1. Get and track proxy addresses from pool's reserve data after pool initialization:
```solidity
function _initializeUsdxlReserve(
    address token,
    IDeployConfigTypes.HypurrDeployRegistry memory deployRegistry
) internal
--- SNIPPED ---
// set reserves configs
_getPoolConfigurator(deployRegistry).initReserves(inputs);
IPoolAddressesProvider poolAddressesProvider = _getPoolAddressesProvider
(deployRegistry);
//@audit DataTypes should be additional imported
DataTypes.ReserveData memory reserveData = IPool
(poolAddressesProvider.getPool()).getReserveData(token);
//@audit Introduce new two state variables to track proxy addresses
usdxlATokenProxy = UsdxlAToken(reserveData.aTokenAddress);
usdxlVariableDebtTokenProxy = UsdxlVariableDebtToken
(reserveData.variableDebtTokenAddress);
// export contract addresses
DeployUsdxlFileUtils.exportContract
(instanceId, "usdxlATokenProxy", _getUsdxlATokenProxy());
DeployUsdxlFileUtils.exportContract(
    instanceId,
    "usdxlVariableDebtTokenProxy",
    _getUsdxlVariableDebtTokenProxy
```
2. Update getter functions to return proxy addresses:
```solidity
function _getUsdxlATokenProxy() internal view returns (address) {
-   return address(usdxlAToken);
+   return address(usdxlATokenProxy);
}
function _getUsdxlVariableDebtTokenProxy() internal view returns (address) {
-   return address(usdxlVariableDebtToken);
+   return address(usdxlVariableDebtTokenProxy);
}
```
3. Update treasury configuration to use proxy:
```solidity
function _setUsdxlAddresses
(IDeployConfigTypes.HypurrDeployRegistry memory deployRegistry)
internal
-   usdxlAToken.updateUsdxlTreasury(deployRegistry.treasury);
+   UsdxlAToken(_getUsdxlATokenProxy()).updateUsdxlTreasury
+   (deployRegistry.treasury);
    UsdxlAToken(_getUsdxlATokenProxy()).setVariableDebtToken
    (_getUsdxlVariableDebtTokenProxy());
    UsdxlVariableDebtToken(_getUsdxlVariableDebtTokenProxy()).setAToken
    (_getUsdxlATokenProxy());
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incorrect address tracking logic in the deployment utilities for the USDXL pool. The internal helper functions that are supposed to return the proxy contracts for the AToken and the VariableDebtToken instead return the addresses of the underlying implementation contracts. Because the pool interacts only with the proxy instances, any configuration that is sent to the implementation address never reaches the live token contracts. As a result, during the reserve initialization the exported deployment artifacts contain the wrong addresses, the pool configurator does not set the AToken and VariableDebtToken parameters, the facilitator entity is not linked to the correct token, and the discount token and strategy settings are left pointing to empty or default contracts. The root cause is the use of the variable usdxlAToken (which holds the implementation) instead of a newly stored variable that captures the proxy address returned by the pool’s getReserveData call. The bug is discovered through static analysis of the deployment scripts and a manual review of the address handling logic. It is subtle because the returned addresses are syntactically valid contract addresses, so the deployment appears to succeed and no immediate runtime error is thrown. From a user’s perspective the USDXL pool behaves as if the token contracts are missing: interest accrual does not happen, users see zero balances for their deposited USDXL, refunds or withdrawals may fail, and the treasury cannot receive fees. The impact is high because the core accounting layer of the protocol is effectively disabled, potentially leading to loss of funds or inability to interact with the pool. The issue can be exploited by an attacker who relies on the assumption that the pool’s tokens are correctly configured; they could deposit funds that never earn interest or trigger unexpected reverts. The proper fix is to query the pool after reserve creation, store the proxy addresses returned in reserveData.aTokenAddress and reserveData.variableDebtTokenAddress, and use those stored proxy addresses in all subsequent configuration calls and artifact exports. This ensures that the pool’s token contracts are correctly initialized, the facilitator entity is linked, and the discount strategy operates on the intended contracts.
