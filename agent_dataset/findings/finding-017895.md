---
id: 17895
severity: "High"
---

# Anyone can wipe complete state of any collateral at any point

## Description

The Clearing House is implemented as an ERC1155. This is used to settle up at the end of an auction. The Clearing House’s token is listed as one of the Consideration Items, and when Seaport goes to transfer it, it triggers the settlement process.

This settlement process includes deleting the collateral state hash from LienToken.sol, burning all lien tokens, deleting the idToUnderlying mapping, and burning the collateral token. **These changes effectively wipe out all record of the liens, as well as removing any claim the borrower has on their underlying collateral.**

After an auction, this works as intended. The function verifies that sufficient payment has been made to meet the auction criteria, and therefore all these variables should be zeroed out.

However, the issue is that there is no check that this safeTransferFrom function is being called after an auction has completed. In the case that it is called when there is no auction, all the auction criteria will be set to 0, and therefore the above deletions can be performed with a payment of 0.

This allows any user to call the `safeTransferFrom()` function for any other user’s collateral. This will wipe out all the liens on that collateral, and burn the borrower’s collateral token, and with it their ability to ever reclaim their collateral.

## Proof of Concept

The flow is as follows:

* safeTransferFrom(offerer, buyer, paymentToken, amount, data)
* _execute(offerer, buyer, paymentToken, amount)
* using the auctionStack in storage, it calculates the amount the auction would currently be listed at
* it confirms that the Clearing House has already received sufficient paymentTokens for this amount
* it then transfers the liquidator their payment (currently 13%)
* it calls `LienToken#payDebtViaClearingHouse()`, which pays back all liens, zeros out all lien storage and deletes the collateralStateHash
* if there is any remaining balance of paymentToken, it transfers it to the owner of the collateral
* it then calls `Collateral#settleAuction()`, which deletes idToUnderlying, collateralIdToAuction and burns the collateral token

In the case where the auction hasn’t started, the `auctionStack` in storage is all set to zero. When it calculates the payment that should be made, it uses `_locateCurrentAmount`, which simply returns `endAmount` if `startAmount == endAmount`. In the case where they are all 0, this returns 0.

The second check that should catch this occurs in `settleAuction()`:

```solidity
    if (
      s.collateralIdToAuction[collateralId] == bytes32(0) &&
      ERC721(s.idToUnderlying[collateralId].tokenContract).ownerOf(
        s.idToUnderlying[collateralId].tokenId
      ) !=
      s.clearingHouse[collateralId]
    ) {
      revert InvalidCollateralState(InvalidCollateralStates.NO_AUCTION);
    }
```

However, this check accidentally uses an `&&` operator instead of a `||`. The result is that, even if the auction hasn’t started, only the first criteria is false. The second is checking whether the Clearing House owns the underlying collateral, which happens as soon as the collateral is deposited in `CollateralToken.sol#onERC721Received()`:

```solidity
      ERC721(msg.sender).safeTransferFrom(
        address(this),
        s.clearingHouse[collateralId],
        tokenId_
      );
```

## Recommendation

Change the check in `settleAuction()` from an AND to an OR, which will block any collateralId that isn’t currently at auction from being settled:

```solidity
    if (
      s.collateralIdToAuction[collateralId] == bytes32(0) ||
      ERC721(s.idToUnderlying[collateralId].tokenContract).ownerOf(
        s.idToUnderlying[collateralId].tokenId
      ) !=
      s.clearingHouse[collateralId]
    ) {
      revert InvalidCollateralState(InvalidCollateralStates.NO_AUCTION);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unauthorized state‑wipe that occurs when the Clearing House settlement function is invoked for a collateral that is not currently in an auction. The contract implements the settlement of an auction through an ERC1155 safeTransferFrom call, which internally calls settleAuction to delete the lien state hash, burn all lien tokens, clear the idToUnderlying mapping and finally burn the collateral token. The root cause is a logical error in the condition that checks whether an auction is active: the code uses a logical AND (&&) instead of a logical OR (||) when verifying that a collateralId has an associated auction and that the Clearing House owns the underlying asset. Because the first part of the condition (collateralIdToAuction[collateralId] == bytes32(0)) is false for a non‑auctioned collateral, the whole expression evaluates to false and the revert is not triggered. Consequently, an attacker can call safeTransferFrom with a payment amount of zero, causing the settlement routine to execute and wipe all lien records and burn the borrower’s collateral token without any payment. The exploit can be performed by any user who knows the collateralId of another user’s deposit; no special privileges are required. The impact is that the borrower loses all claim to their underlying NFT, the lien information disappears, and any funds that would have been returned to the borrower are never transferred, effectively making the collateral disappear. This situation occurs whenever safeTransferFrom is called on a collateral that has not entered an auction, i.e., before the auction start or after it has been cleared. All borrowers who have deposited collateral and all lenders holding liens on that collateral are affected. The issue was discovered during a security audit by Code4rena, where the logical condition was identified as incorrectly using &&. The bug is subtle because the settlement flow appears normal and the zero‑payment passes the existing checks, making it easy to miss during functional testing. To remediate, the condition should be changed to use an OR, ensuring that the function reverts whenever the collateral is not currently in an auction, thereby preventing unauthorized deletion of state. This class of bug falls under improper access control and missing state validation, where critical state‑mutating operations are performed without confirming the required pre‑conditions, leading to loss of assets and violation of the protocol’s accounting guarantees. From a user’s perspective the symptom is that after initiating a transfer they see their collateral token balance drop to zero, receive no refund, and are unable to reclaim the underlying NFT, contrary to the expectation that a transfer only moves ownership after a successful auction.
