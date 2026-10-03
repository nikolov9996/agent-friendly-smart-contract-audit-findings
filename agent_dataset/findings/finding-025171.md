---
id: 25171
severity: "Crit/High"
---

# Lister is overpaying during the cancel of his listing on Listings::cancelListings().

## Description



## Proof of Concept

No PoC needed.

## Impact

The impact of this serious vulnerability is that the user is forced to double pay the tax that has been used for the duration that his `listing` was up. He, firstly, paid for it by not taking it and now, when he cancels the `listing`, he has to pay it again out of his own pocket. This results to unfair **loss of funds** for whoever tries to cancel his `listing`.

## Recommendation

To mitigate this vulnerability successfully, consider not requiring user to return the `fee` variable as well :

```diff
    function cancelListings(address _collection, uint[] memory _tokenIds, bool _payTaxWithEscrow) public lockerNotPaused {
        uint fees;
        uint refund;

        for (uint i; i < _tokenIds.length; ++i) {
           // ...
        }

        // cache
        ICollectionToken collectionToken = locker.collectionToken(_collection);

        // Burn the ERC20 token that would have been given to the user when it was initially created
-        uint requiredAmount = ((1 ether * _tokenIds.length) * 10 ** collectionToken.denomination()) - refund;
+        uint requiredAmount = ((1 ether * _tokenIds.length) * 10 ** collectionToken.denomination()) - refund - fees;
        payTaxWithEscrow(address(collectionToken), requiredAmount, _payTaxWithEscrow);
        collectionToken.burn(requiredAmount + refund);

        // ...
    }
```
