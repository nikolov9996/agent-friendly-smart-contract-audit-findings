---
id: 25048
severity: "Low/Info"
---

# Some view functions will not work under certain conditions

## Description



## Proof of Concept

## Vulnerability Detail

The functions below when there is no debt or position, most likely when the Den hasn't been opened or when the Vault was just deployed.

```solidity
function getStrategyCR() public view returns (uint256) {
    return (getMarginValue() + getExposureBalance()) * WAD / getDebtBalance();
}

function exposurePositionWeight() public view returns (uint256) {
    return getExposureValue() * WAD / getCurrentPositionValue();
}

function collateralPositionWeight() public view returns (uint256) {
    return WAD - exposurePositionWeight();
}

function getStrategyLeverage() public view returns (uint256) {
    uint256 positionValue = getCurrentPositionValue();
    return positionValue * WAD / (positionValue - getDebtBalance());
}
```

## Impact

View function reverts.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR742](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR742>) [https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR746](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR746>) [https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR753](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR753>)

## Recommendation

Handle these cases.
