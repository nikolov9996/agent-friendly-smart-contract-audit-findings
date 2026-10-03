---
id: 25026
severity: "Medium"
---

# It's impossible to retrieve collected fines from the yield staking contract

## Description



## Proof of Concept

If `botAdmin` forcefully unstakes a position, a staker will have to pay an additional fine when the stake is repayed:

```
  function _repay(uint32 poolId, address nft, uint256 tokenId) internal virtual {
    ---SNIP---

    vars.nftDebt = _getNftDebtInUnderlyingAsset(sd);
>>  vars.nftDebtWithFine = vars.nftDebt + sd.unstakeFine;

    // compute repay value
    if (vars.claimedYield >= vars.nftDebtWithFine) {
      vars.remainAmount = vars.claimedYield - vars.nftDebtWithFine;
    } else {
      vars.extraAmount = vars.nftDebtWithFine - vars.claimedYield;
    }

    // transfer eth from sender
    if (vars.extraAmount > 0) {
>>    underlyingAsset.safeTransferFrom(vars.nftOwner, address(this), vars.extraAmount);
    }

    if (vars.remainAmount > 0) {
      underlyingAsset.safeTransfer(vars.nftOwner, vars.remainAmount);
    }

    // repay lending pool
>>  poolYield.yieldRepayERC20(poolId, address(underlyingAsset), vars.nftDebt);

    poolYield.yieldSetERC721TokenData(poolId, nft, tokenId, false, address(underlyingAsset));

    // update shares
    accountYieldInWithdraws[address(vars.yieldAccout)] -= sd.withdrawAmount;
    totalDebtShare -= sd.debtShare;

    delete stakeDatas[nft][tokenId];

    emit Repay(msg.sender, nft, tokenId, vars.nftDebt);
  }
```

Note that the user's total debt consists of the actual NFT debt and the fine. When the stake is paid off, only the `nftDebt` is sent to the pool, and the `unstakeFine` remains in the contract. However, there are no functions that send the collected funds to the admin, and so they will remain in the contract forever.

## Recommendation

Implement a function that allows admin to collect fines from the yield staking contract.
