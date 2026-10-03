---
id: 25293
severity: "Low/Info"
---

# Unhandled rounding error in DistributionVault.getClaimable leads to locked dust

## Description

The [DistributionVault.getClaimable](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/DistributionVault.sol#L129>) function rounds down during the division operation used to calculate claimable, resulting in dust amounts being locked in DistributionVault.

```solidity
function getClaimable( address token_, address account_, uint256 startEpoch_, uint256 endEpoch_ ) public view returns (uint256 claimable_) {
    // ...
claimable_ += (distributionOfAt[token_][startEpoch_ + index_] *
balance_) / totalSupply_;
}
}
```

Every single token in the contract is meant to be retrieved by a specific user at a specific past epoch. This means that any rounding errors that might occur will lead to dust amounts being locked in the contract as DistributionVault does not have any mechanism that enables these funds to be retrieved.

The impact of this issue depends on a couple of points:

1. As token precision decreases, 1 unit of that token is more valuable than 1 unit of a token with higher precision. This will make rounding errors in the claimable calculation more

expensive for lower decimal tokens. So, the impact of this issue increases as the precision of the token claimed decreases.

2. The fact that the protocol makes a rounding down division for every past epoch will also increase the impact of this issue comparing to other vaults, as the dust amount will grow for every epoch iteration.
3. As the total supply of ZERO is more thinly distributed among holders, the amount of dust locked in the Vault will also increase:

- If no ZERO holder has more than 10% of the total supply, 10 wei may be locked in the contract per epoch;
- If no ZERO holder has more than 5% of the total supply, 20 wei may be locked in the contract per epoch;
- etc

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
