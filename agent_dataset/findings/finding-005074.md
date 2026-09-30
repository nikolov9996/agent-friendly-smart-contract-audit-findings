---
id: 5074
severity: "High"
---

# Calculating interest without considering the collateral decimals

## Description

The outstandingInterestOf() function converts the interest from the TCAP amount to the collateral amount. However, it does not consider TCAP and collateral decimals when converting, which results in a rather large interest calculated when using low-decimal tokens such as USDC/USDT as collateral.
```solidity
function outstandingInterestOf(address user, uint96 pocketId) public view returns (uint256) {
    MintData storage $ = _getVaultStorage().mintData;
    uint256 interestAmount = $.interestOf(_toMintId(user, pocketId));
    return interestAmount * TCAPV2.latestPrice() / latestPrice();
}
```

## Proof of Concept

The proof of concept shows that when collateral is 6 decimals, outstandingInterest() returns 0.1e18 (should be 0.1e6), and collateralOf will underflow:
```solidity
function test_poc() public {
    address user = makeAddr("user");
    uint256 amount = 100e6;
    deposit(user, amount);
    vm.prank(user);
    vault.mint(pocketId, 10e18);
    uint timestamp = 365 days;
    vm.warp(timestamp);
    uint256 outstandingInterest = vault.outstandingInterestOf(user, pocketId);
    console.logUint(outstandingInterest); // 0.1e18
    console.logUint(vault.collateralOf(user, pocketId)); // [FAIL. Reason: panic: arithmetic underflow or overflow (0x11)]
}
```

## Recommendation

Considering collateral and TCAP decimals in outstandingInterestOf()
```solidity
function outstandingInterestOf(address user, uint96 pocketId) public view returns (uint256) {
    MintData storage $ = _getVaultStorage().mintData;
    uint256 interestAmount = $.interestOf(_toMintId(user, pocketId));
    uint256 assetDecimals = _getVaultStorage().oracle.assetDecimals();
    return interestAmount * TCAPV2.latestPrice() * 10 ** assetDecimals / latestPrice() / 10 ** 18;
    // return interestAmount * TCAPV2.latestPrice() / latestPrice();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a decimal‑handling error in the function that reports a user’s accrued interest. The routine converts the raw interest amount, which is expressed in the protocol’s native token (TCAP), into the amount of the collateral token by multiplying with the TCAP price and dividing by the collateral price. However, it does not adjust for the differing number of decimal places between TCAP (18 decimals) and many common collateral tokens such as USDC or USDT (6 decimals). Because the conversion omits the scaling factor for the collateral’s decimals, the computed interest is inflated by a factor of 10^(18‑collateralDecimals). When a low‑decimal token is used as collateral, the function returns a value that is orders of magnitude larger than the true amount. This inflated interest is later used in the collateral accounting routine, causing the collateral balance to underflow or become negative, which in practice manifests as the user’s collateral disappearing or the contract reverting with an arithmetic under‑flow error. The bug can be triggered simply by depositing a 6‑decimal collateral, minting TCAP, advancing time so that interest accrues, and then calling the interest‑query function; the returned interest will be 10^12 times larger than expected, leading to a failed collateral withdrawal. The impact is severe: users may lose access to their deposited funds, the protocol’s accounting invariants break, and the overall trust in the system is compromised. The condition for exploitation is any scenario where the collateral token does not share the 18‑decimal precision of TCAP, which is common in stablecoins. The affected parties are depositors, the protocol’s liquidity pool, and any downstream contracts that rely on the reported collateral amount. The issue was discovered during a manual audit when the auditor observed that the function returned a value with 18‑decimal scaling even for a 6‑decimal asset, and a proof‑of‑concept test demonstrated an arithmetic underflow in the collateral balance. The problem is subtle because the returned number is still a valid uint256 and does not immediately cause a revert, making it easy to miss during casual testing. To remediate, the conversion must incorporate both the collateral token’s decimal count and the TCAP token’s 18‑decimal base, typically by multiplying the raw interest by the collateral’s decimal factor (10**assetDecimals) and dividing by 10**18 after applying price ratios. This ensures that the interest is expressed in the correct unit, preserving the integrity of collateral accounting and preventing funds from disappearing. The bug belongs to the broader class of unit‑conversion or decimal‑mismatch vulnerabilities, where mismatched token precisions lead to incorrect financial calculations and potential loss of assets.
