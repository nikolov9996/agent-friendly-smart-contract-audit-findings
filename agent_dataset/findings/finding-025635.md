---
id: 25635
severity: "Low/Info"
---

# Struct order in MetavaultsRegistry could be switched for better readability

## Description



## Proof of Concept

## Vulnerability Detail

```solidity
    // keccak256(abi.encode(uint256(keccak256("spectra.metavault.markets")) - 1)) & ~bytes32(uint256(0xff))
    bytes32 private constant MARKET_INFOS_LOCATION =
        0xed37d1382a6bfbb25f83b33532c04381222190008afbfed9374fd7204ef8d200;

    // keccak256(abi.encode(uint256(keccak256("spectra.metavault.configs")) - 1)) & ~bytes32(uint256(0xff))
    bytes32 private constant MV_CONFIGS_LOCATION =
        0xc529114c4cac99852bfd8483ed99a3cf970cf4610e078f8f8ea71d2fe61b1c00;

    // keccak256(abi.encode(uint256(keccak256("spectra.metavault.bridge")) - 1)) & ~bytes32(uint256(0xff))
    bytes32 private constant BRIDGE_CONFIGS_LOCATION =
        0xa3601e533f2d68c8147877ed38f63d7abe628c505c72f827dccfd47c7297f100;

    struct MetavaultsRegistryState {
        mapping(address => MetavaultConfig) metavaults;
    }

    struct MarketInfosState {
        mapping(address => address) ptToMarket;
        mapping(address => address) ytToMarket;
        mapping(address => PoolInfos) poolToPoolInfos;
    }

    struct MetavaultsBridgeState {
        mapping(address => MetavaultBridgeConfig) metavaultBridgeConfigs;
    }

    function _getMarketInfosStorage() private pure returns (MarketInfosState storage $) {
        assembly {
            $.slot := MARKET_INFOS_LOCATION
        }
    }

    function _getMvConfigStorage() private pure returns (MetavaultsRegistryState storage $) {
        assembly {
            $.slot := MV_CONFIGS_LOCATION
        }
    }

    function _getMvBridgeStorage() private pure returns (MetavaultsBridgeState storage $) {
        assembly {
            $.slot := BRIDGE_CONFIGS_LOCATION
        }
    }
```

## Impact

Readability

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R17-R58](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R17-R58>)

## Recommendation

Change the struct order
