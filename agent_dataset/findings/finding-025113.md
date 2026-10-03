---
id: 25113
severity: "Crit/High"
---

# Incoming Redemption Assets not being tracked when repurchase is called

## Description



## Proof of Concept

## Vulnerability Detail

Users deposit redemption asset via deposit to get back Cover Token + DepegSwap which can be redeemed back using various combinations.

1. Redeem with CoverToken + DepegSwap ( only before expiry of DS )
2. Redeem with DepegSwap + Pegged Asset ( only before expiry of DS )
3. Redeem with CoverToken ( only after expiry )

Is users use 2. as a means to redeem deposited RA, they can repurchase DepegSwap + Pegged Asset back using `repurchase()` The `repurchase()` function is designed for getting back a combination of DepegSwap + Pegged Asset by giving Redemption Asset.

Incoming and outgoing RA is tracked via PsmRedemptionAssetManager struct attached with State struct. Consider the system before expiry. Let's look at all the places where RA can come and go and how internal tracking is changing respectively.

1. deposit() : ra increased
2. redeem with DS + PA : ra decreased
3. redeem with CT + DS : ra decreased Everytime there is incoming of ra, the contracts increases internal state variable ( `locked`) with that amount.

```Solidity
struct PsmRedemptionAssetManager {
    address _address;
    uint256 locked;
    uint256 free;
}
```

But this is not increased when ra comes with `repurchase()` . This can be problematic after time of expiry. After expiry, when users redeems with ct by calling `redeemWithCt()` it internally invokes `_separateLiquidity()`.

```Solidity
    function _separateLiquidity(State storage self, uint256 prevIdx) internal {
        if (self.psm.liquiditySeparated.get(prevIdx)) {
            return;
        }

        DepegSwap storage ds = self.ds[prevIdx];
        Guard.safeAfterExpired(ds);

        uint256 availableRa = self.psm.balances.ra.convertAllToFree();
        uint256 availablePa = self.psm.balances.paBalance;

        self.psm.poolArchive[prevIdx] = PsmPoolArchive(availableRa, availablePa, IERC20(ds.ct).totalSupply());

        // reset current balances
        self.psm.balances.ra.reset();
        self.psm.balances.paBalance = 0;

        self.psm.liquiditySeparated.set(prevIdx);
    }
```

In this function all the accumulated ra goes to pool archive. This is achieved by zeroing out the variable that was tracking incoming and outgoing ra ( by `reset()`) and storing it in PoolArchive.

But since repurchase does not change this internal variable, at the time of `_separateLiquidity()` , actual ra in the system will be much more than what is expected.

## Impact

Since protocol's internal tracking assumes less ra in the system than the actual amount, the remaining amount will be stuck in the contract causing direct loss of funds.

## Code Snippet

[https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/libraries/PsmLib.sol#L293-L322](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/main/Depeg-swap/contracts/libraries/PsmLib.sol#L293-L322>)

## Recommendation

Increase locked ra amount whenever repurchase is called by calling `lockFrom` instead of `lockUnchecked()`
