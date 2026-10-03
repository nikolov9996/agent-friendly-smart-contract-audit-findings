---
id: 25701
severity: "Medium"
---

# Malicious users could lock in the NAV/Share of the DV to cause the loss of fees

## Description



## Proof of Concept

## Vulnerability Detail

The `_collectFees` function only collects fees whenever the NAV/Share exceeds the last NAV/Share.

During initialization, the `navPerShareHighMark` is set to `1`, effectively 1 ETH per share (1:1 ratio). Assume the following:

- It is at the early stage, and only a few shares (0.5 shares) were minted in the LMPVault
- There is a sudden increase in the price of an LP token in a certain DV (Temporarily)
- `performanceFeeBps` is 10%

In this case, the debt value of DV's shares will increase, which will cause LMPVault's debt to increase. This event caused the `currentNavPerShare` to increase to `1.4` temporarily.

Someone calls the permissionless `updateDebtReporting` function. Thus, the profit will be `0.4 ETH * 0.5 Shares = 0.2 ETH`, which is small due to the number of shares (0.5 shares) in the LMPVault at this point. The fee will be `0.02 ETH` (~40 USD). Thus, the fee earned is very little and almost negligible.

At the end of the function, the `navPerShareHighMark` will be set to `1.4,` and the highest NAV/Share will be locked forever. After some time, the price of the LP tokens fell back to its expected price range, and the `currentNavPerShare` fell to around `1.05`. No fee will be collected from this point onwards unless the NAV/Share is raised above `1.4`.

It might take a long time to reach the `1.4` threshold, or in the worst case, the spike is temporary, and it will never reach `1.4` again. So, when the NAV/Share of the LMPVault is 1.0 to 1.4, the protocol only collects `0.02 ETH` (~40 USD), which is too little.

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L800](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L800>)

```typescript
function _collectFees(uint256 idle, uint256 debt, uint256 totalSupply) internal {
    address sink = feeSink;
    uint256 fees = 0;
    uint256 shares = 0;
    uint256 profit = 0;

    // If there's no supply then there should be no assets and so nothing
    // to actually take fees on
    if (totalSupply == 0) {
        return;
    }

    uint256 currentNavPerShare = ((idle + debt) * MAX_FEE_BPS) / totalSupply;
    uint256 effectiveNavPerShareHighMark = navPerShareHighMark;

    if (currentNavPerShare > effectiveNavPerShareHighMark) {
        // Even if we aren't going to take the fee (haven't set a sink)
        // We still want to calculate so we can emit for off-chain analysis
        profit = (currentNavPerShare - effectiveNavPerShareHighMark) * totalSupply;
        fees = profit.mulDiv(performanceFeeBps, (MAX_FEE_BPS ** 2), Math.Rounding.Up);
        if (fees > 0 && sink != address(0)) {
            // Calculated separate from other mints as normal share mint is round down
            shares = _convertToShares(fees, Math.Rounding.Up);
            _mint(sink, shares);
            emit Deposit(address(this), sink, fees, shares);
        }
        // Set our new high water mark, the last nav/share height we took fees
        navPerShareHighMark = currentNavPerShare;
        navPerShareHighMarkTimestamp = block.timestamp;
        emit NewNavHighWatermark(currentNavPerShare, block.timestamp);
    }
    emit FeeCollected(fees, sink, shares, profit, idle, debt);
}
```

## Impact

Loss of fee. Fee collection is an integral part of the protocol; thus the loss of fee is considered a High issue.

## Code Snippet

[https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L800](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/vault/LMPVault.sol#L800>)

## Recommendation

Consider implementing a sophisticated off-chain algorithm to determine the right time to lock the `navPerShareHighMark` and/or restrict the access to the `updateDebtReporting` function to only protocol-owned addresses.
