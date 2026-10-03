---
id: 25631
severity: "Low/Info"
---

# MetavaultsRegistry::registerChain() allows chain id 0, which doesn't exist, but would be problematic

## Description



## Proof of Concept

## Vulnerability Detail

`MetavaultsRegistry:unregisterChain()` reverting.

```solidity
    function unregisterChain(
        address metavault,
        uint256 chainId
    ) external restricted onlyRegistered(metavault) {
        MetavaultConfig storage config = _getMvConfigStorage().metavaults[metavault];
        if (config.chainConfigs[chainId].chainId == 0)
            revert ChainNotRegistered(metavault, chainId);
```

## Impact

Chain id == 0, doesn't exist so it would be admin mistake.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R202](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R202>)

## Recommendation

Don't allow chain id == 0 in `MetavaultsRegistry::registerChain()`.
