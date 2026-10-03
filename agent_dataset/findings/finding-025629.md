---
id: 25629
severity: "Low/Info"
---

# address(0) check could be added to MetavaultRegistry::registerMetavault()

## Description



## Proof of Concept

## Vulnerability Detail

```solidity
function registerMetavault(address metavault, address[] memory markets) external restricted {
    MetavaultConfig storage config = _getMvConfigStorage().metavaults[metavault];
    if (config.metavault != address(0)) revert MetavaultAlreadyRegistered(metavault);

    config.metavault = metavault;
    config.chainsCount = 1;

    // register the first markets to whitelist during the metavault registration
    for (uint256 i = 0; i < markets.length; i++) {
        config.markets.push(markets[i]);
        MarketConfig memory marketConfig = MarketConfig({isRegistered: true});
        config.marketConfigs[markets[i]] = marketConfig;
        _registerPoolInfos(markets[i]);
        emit MarketRegistered(metavault, markets[i]);
    }

    // Register current chain
    MetavaultChainConfig memory chainConfig = MetavaultChainConfig({
        chainId: block.chainid,
        remoteMetavaultAddress: metavault
    });
    config.chains.push(chainConfig);
    config.chainConfigs[block.chainid] = chainConfig;
    emit ChainRegistered(metavault, block.chainid, metavault);
    emit MetavaultRegistered(metavault);
}
```

## Impact

It would be an admin mistake.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R83](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R83>)

## Recommendation

Check if the metavault is not the zero address.
