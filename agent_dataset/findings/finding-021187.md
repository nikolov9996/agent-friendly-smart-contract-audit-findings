---
id: 21187
severity: "High"
---

# Base tokens like USDT, USDC having different decimals on different chains can have their TVL updated incorrectly

## Description

Tokens like [USDT, USDC](https://bscscan.com/address/0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d#readProxyContract#F3) on the BSC chain have 18 decimals while the “Base” blockchain which is being used as the root/base chain uses 6 decimals (see [here](https://basescan.org/token/0x833589fcd6edb6e08f4c7c32d4f71b54bda02913#readProxyContract)).

The issue is that when the TVL is updated on the base chain by sending a cross-chain message call from OmnichainManagerNormalChain.sol contract to OmnichainManagerBaseChain.sol contract, the TVL is recorded in the holding position with 18 decimals instead of scaling it down to 6 decimals.

Due to this, whenever the accounting manager retrieves the [TVL()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/accountingManager/AccountingManager.sol#L627C1-L630C6) through function [totalAssets()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/accountingManager/AccountingManager.sol#L592) (overriden from ERC4626), the TVLHelper contract would loop through all holding positions and sum them up in order to be used in vault operations like minting shares etc. This would be problematic since the tvl is 1e12 decimals more than the actual of 1e6. This breaks the accounting in the accounting manager contract.

## Proof of Concept

Here’s the whole process:

1. Manager calls function [updateTVLInfo()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/OmniChainHandler/OmnichainManagerNormalChain.sol#L28) on the OmnichainManagerNormalChain.sol contract on the BSC chain.
2. On Line 29, it calls the getTVL() function that loops through all the holding positions for the base token and vaultId.
3. The value is returned (in 18 decimals since we’re on BSC) and stored in `tvl` on Line 29.

Line 30 calls the updateTVL() function on the lzhelper contract, which sends the cross-chain message with the tvl update.

```solidity
File: OmnichainManagerNormalChain.sol
19:     function getTVL() public view returns (uint256) {
20:         (, address baseToken) = registry.getVaultAddresses(vaultId);
21:         return TVLHelper.getTVL(vaultId, registry, baseToken);
22:     }
23:     /**
24:      * Triggers an update of the vault's TVL information, sending the latest data to the base chain via the LZHelperSender contract.
25:      * This function is restricted to be called by managers only, ensuring that TVL updates are controlled and authorized.
26:      */
27: 
28:     function updateTVLInfo() external onlyManager {
29:         uint256 tvl = getTVL();
30:         LZHelperSender(lzHelper).updateTVL(vaultId, tvl, block.timestamp);
31:     }
```

2. The call arrives on the base chain by LZ calling the [_lzReceive()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/LZHelpers/LZHelperReceiver.sol#L65) function, which calls the [updateTVL()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/helpers/OmniChainHandler/OmnichainManagerBaseChain.sol#L32) function on the OmnichainManagerBaseChain.sol contract.
3. On Line 39, the `tvl` variable is stored as is with the 18 decimals incorrectly.

```solidity
File: OmnichainManagerBaseChain.sol
32:     function updateTVL(uint256 chainId, uint256 tvl, uint256 updateTime) external nonReentrant {
33:         if (msg.sender != lzHelper) revert IConnector_InvalidSender();
34:         
35:         registry.updateHoldingPostionWithTime(
36:             vaultId,
37:             registry.calculatePositionId(address(this), OMNICHAIN_POSITION_ID, abi.encode(chainId)),
38:             "",
39:             abi.encode(tvl),
40:             tvl <= DUST_LEVEL,
41:             updateTime
42:         );
43:     }
```

3. Now when the [totalAssets()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/accountingManager/AccountingManager.sol#L591) function in the accounting manager calls the [TVL()](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/accountingManager/AccountingManager.sol#L627) function, it loops through the holding positions in the TVLHelper contract and sums up the TVL incorrectly.

```solidity
function getTVL(uint256 vaultId, PositionRegistry registry, address baseToken) public view returns (uint256) {
    uint256 totalTVL;
    uint256 totalDebt;
    HoldingPI[] memory positions = registry.getHoldingPositions(vaultId);
    for (uint256 i = 0; i < positions.length; i++) {
        if (positions[i].calculatorConnector == address(0)) {
            continue;
        }
        uint256 tvl = IConnector(positions[i].calculatorConnector).getPositionTVL(positions[i], baseToken);
        bool isPositionDebt = registry.isPositionDebt(vaultId, positions[i].positionId);
        if (isPositionDebt) {
            totalDebt += tvl;
        } else {
            totalTVL += tvl;
        }
    }
    if (totalTVL < totalDebt) {
        return 0;
    }
    return (totalTVL - totalDebt);
}
```

Through this we observe how incorrect tvl is reported from the normal chain to the base chain, which hugely affects the value retrieved by function totalAssets() for ERC4626 vault operations.

## Recommendation

Keep track of the decimals of tokens on other chains in a mapping. If they are more or less, consider scaling them once the tvl update is received on the base chain.

Fix in commit 58537ef76afa048745f85a31cb7a0aa3eb6b300b.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a cross‑chain accounting error caused by mismatched token decimal definitions between the source chain (e.g., BSC) and the base chain (Base). Tokens such as USDT and USDC use 18 decimals on BSC while the same token is defined with 6 decimals on Base. When the OmnichainManager on the normal chain calculates the total value locked (TVL) it reads the amount with 18‑decimal precision and forwards this raw number to the OmnichainManager on the base chain without applying any scaling. The base‑chain contract stores the received value directly, treating it as if it were already expressed in the base‑chain’s 6‑decimal format. As a result the recorded TVL is inflated by a factor of 10¹². The AccountingManager later aggregates TVL values from all holding positions through its totalAssets() function (overridden from ERC4626). Because the stored TVL is three orders of magnitude larger than the real asset amount, totalAssets() returns an exaggerated figure, which is then used for vault operations such as minting shares, calculating redemption values, and dust‑level checks. This mis‑calculation can allow users to mint more shares than the underlying collateral actually supports, potentially leading to under‑collateralised withdrawals and loss of funds for honest participants. The bug manifests only when a base token has different decimal precision across chains and a TVL update is sent via the cross‑chain messaging path; it does not affect tokens with identical decimals. The issue was discovered during a security audit that examined the cross‑chain TVL update flow and identified that the tvl variable was encoded and stored without any decimal conversion. It is hard to notice because the inflated TVL may still appear as a plausible large number in UI dashboards, and there is no explicit sanity check that validates the magnitude against expected token precision. To remediate, the protocol should maintain a mapping of token decimals per chain and apply appropriate scaling (either down‑scaling from 18 to 6 decimals or up‑scaling as needed) before persisting the TVL on the base chain. This ensures that accounting calculations reflect the true asset value, preserving the integrity of share minting, redemption, and overall vault safety.
