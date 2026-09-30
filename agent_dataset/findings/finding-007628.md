---
id: 7628
severity: "High"
---

# Collateralization ratio can be broken by users redeeming deposits for ETH

## Description

A key property of the DYAD system is that the collateralization ratio (300%) is maintained. This means that for every 1 DYAD in circulation, there is 3x as much ETH (priced in USD) in the vault.

This invariant is enforced in the withdraw() function, which stops users from minting more DYAD when such a mint would break the invariant:
```solidity
function withdraw(uint from, address to, uint amount) external
    isNftOwnerOrHasPermission(from, Permission.WITHDRAW)
    isUnlocked(from)
{
    _subDeposit(from, amount);

    uint collatVault    = address(this).balance * _getEthPrice()/1e8;
    uint newCollatRatio = collatVault.divWadDown(dyad.totalSupply() + amount);
    if (newCollatRatio < MINCOLLATERIZATIONRATIO) { revert CrTooLow(); }
    ...
}
```

However, the same check is not enforced when redeeming ETH out of the contract. Since a key goal is keeping the ratio of circulating DYAD and ETH bounded by this ratio, it is crucial that we enforce this check on both DYAD minting and ETH redeeming.

## Proof of Concept

Here is a test showing that we can get the collateralization ratio as low as 1:1 by withdrawing all non-minted deposits:
```solidity
function test_CollateralizationRatioBrokenOnRedeemDeposit() public {
    // We deposit 5000 in totalDeposit and mint 1000 of them. Ratio is $5000 of ETH / 1000 supply.
    uint id1 = dNft.mint{value: 5 ether}(address(this));
    dNft.withdraw(id1, address(this), 1000e18);
    console.log(_calculateCollateralizationRatio()); // returns 5e18 - success

    // We can now withdraw all the remaining ETH with no check.
    dNft.redeemDeposit(id1, address(1), 4000e18);
    console.log(_calculateCollateralizationRatio()); // returns 1e18 - uh oh
}

function _calculateCollateralizationRatio() internal returns(uint) {
    uint ETH_PRICE = 1000 * 1e8;
    uint MINCOLLATERIZATIONRATIO = 3e18;
    uint collatVault = address(dNft).balance * ETH_PRICE/1e8;
    uint newCollatRatio = FixedPointMathLib.divWadDown(collatVault, dyad.totalSupply());
    return newCollatRatio;
}
```

## Recommendation

I would recommend moving the collateralization logic into a modifier, as follows:
```solidity
modifier collateralizationCheck(uint amountMinted, uint amountRedeemed) {
    uint collatVault = (address(this).balance - dyad2eth(amountRedeemed)) * _getEthPrice() / 1e8;
    if (dyad.totalSupply() > 0) {
        uint newCollatRatio = collatVault.divWadDown(dyad.totalSupply() + amountMinted);
        if (newCollatRatio < MINCOLLATERIZATIONRATIO) { revert CrTooLow(); }
    }
    _;
}
```
This modifier could then be implemented by both the functions listed below:
```solidity
function withdraw(uint from, address to, uint amount) external
    isNftOwnerOrHasPermission(from, Permission.WITHDRAW)
    isUnlocked(from)
    collateralizationCheck(amount, 0)
{ ... }
```

and

```solidity
function redeemDeposit(uint from, address to, uint amount) external
    isNftOwnerOrHasPermission(from, Permission.REDEEM)
    isUnlocked(from)
    collateralizationCheck(0, amount)
    returns (uint) { ... }
```

You'll note a few small additional changes:
We need to check whether dyad.totalSupply() == 0 before performing this logic, because the collateralization ratio is infinite before any DYAD has been minted, and we will revert when dividing by zero in our check. This is included in the modifier above.
Your existing testCannot_WithdrawCrTooLow test is broken by this change, but it appears this test is incorrect. It is expecting a revert when a dNFT is minted and all is withdrawn, but this situation should be fine, as it does not break any collateralization ratio is there is no DYAD yet in existence.

Review
Fix confirmed in [PR #20](https://github.com/DyadStablecoin/contracts-v3/pull/20/files) by including a mechanism to check individual user collateralization ratios on withdrawals.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a missing collateralization check when users redeem ETH from the DYAD vault. The DYAD system is designed to keep a 300% collateralization ratio, meaning that the USD value of ETH held in the contract must be at least three times the total DYAD supply. This invariant is enforced in the withdraw() function, which prevents minting additional DYAD if the resulting ratio would fall below the minimum. However, the redeemDeposit() function, which allows users to withdraw ETH that they previously deposited, does not perform the same ratio calculation before releasing the funds. The root cause is that the invariant enforcement logic is only applied to the minting path and not to the redemption path, leaving a gap in the accounting of the vault’s collateral. An attacker can exploit this by first depositing ETH, minting a portion of DYAD, and then calling redeemDeposit to withdraw the remaining ETH without any ratio check. Because the contract’s balance is reduced while the DYAD supply remains unchanged, the collateralization ratio can drop from the intended 3:1 to as low as 1:1, effectively breaking the economic guarantee of the stablecoin. The impact is that the protocol becomes under‑collateralized, which can lead to loss of confidence, potential de‑pegging of the token, and exposure of token holders to loss of value. The condition under which this occurs is any situation where a user with a non‑zero deposit calls redeemDeposit after minting DYAD; the bug is triggered regardless of the amount redeemed as long as the contract’s balance falls below the required threshold. All DYAD holders, the protocol’s governance, and any downstream applications that rely on the stablecoin’s backing are affected because the system no longer guarantees the promised collateral ratio. The issue was discovered during a security audit when a test case demonstrated that after withdrawing a portion of the deposited ETH, the subsequent call to redeemDeposit could reduce the ratio to 1:1 without any revert. The bug is subtle because the contract does not emit an error; the ratio appears correct after the initial mint, and only after redemption does the invariant break, making it easy to miss in manual reviews. The recommended fix is to abstract the collateralization logic into a shared modifier that is applied to both withdraw() and redeemDeposit(), ensuring that any change to the vault’s ETH balance is evaluated against the DYAD supply before the operation proceeds. The modifier should also handle the edge case where the total DYAD supply is zero to avoid division‑by‑zero errors. By enforcing the check on both paths, the protocol maintains its economic guarantees and prevents the under‑collateralization scenario that currently allows funds to disappear from the backing pool.
