---
id: 25032
severity: "Medium"
---

# Borrower can prevent yield position repayment and closure by the bot

## Description



## Proof of Concept

Let's take a closer look at the `_repay` function:

```
  function _repay(uint32 poolId, address nft, uint256 tokenId) internal virtual {
    RepayLocalVars memory vars;
    ---SNIP---
    // withdraw yield from protocol and repay if possible

    vars.claimedYield = protocolClaimWithdraw(sd);

    vars.nftDebt = _getNftDebtInUnderlyingAsset(sd);
    vars.nftDebtWithFine = vars.nftDebt + sd.unstakeFine;

    // compute repay value
    if (vars.claimedYield >= vars.nftDebtWithFine) {
      vars.remainAmount = vars.claimedYield - vars.nftDebtWithFine;
    } else {
>>    vars.extraAmount = vars.nftDebtWithFine - vars.claimedYield;
    }

    // transfer eth from sender
    if (vars.extraAmount > 0) {
>>    underlyingAsset.safeTransferFrom(vars.nftOwner, address(this), vars.extraAmount);
    }

    if (vars.remainAmount > 0) {
      underlyingAsset.safeTransfer(vars.nftOwner, vars.remainAmount);
    }

    // repay lending pool
    poolYield.yieldRepayERC20(poolId, address(underlyingAsset), vars.nftDebt);

    poolYield.yieldSetERC721TokenData(poolId, nft, tokenId, false, address(underlyingAsset));

    // update shares
    accountYieldInWithdraws[address(vars.yieldAccout)] -= sd.withdrawAmount;
    totalDebtShare -= sd.debtShare;

    delete stakeDatas[nft][tokenId];

    emit Repay(msg.sender, nft, tokenId, vars.nftDebt);
  }
```

If the yield collected by the position is not enough to cover the entire debt and fines, the protocol will attempt to collect `extraAmount` from the position owner, but he may revoke ERC20 approval and cancel the `safeTransferFrom` function call. As a result, `nftDebt` will not be repaid and will continue to collect interest, increasing the protocol's losses.

## Recommendation

It is recommended to separate the logic of debt repayment and NFT unlocking. The `_repay` function will reduce the debt of the position using the collected yield and unlock the NFT only if `extraAmount` is zero. In case `extraAmount` is greater than zero, leave the token locked and allow the NFT owner to unlock it only after he has repaid the remaining debt.
