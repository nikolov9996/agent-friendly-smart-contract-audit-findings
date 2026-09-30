---
id: 3089
severity: "High"
---

# The Bridging Process will revert if the Collection is matched on the destination chain and not matched on the source chain

## Description

When Bridging Collections L1<->L2, we are checking if that NFT collection has a pair on the destination chain or not. and if it has an address on the destination, then we use it instead of redeploying new one.

CollectionManager.sol#L111-L149
```solidity
function _verifyRequestAddresses(address collectionL1Req, snaddress collectionL2Req) ... {
    address l1Req = collectionL1Req;
    uint256 l2Req = snaddress.unwrap(collectionL2Req);
    address l1Mapping = _l2ToL1Addresses[collectionL2Req];
    uint256 l2Mapping = snaddress.unwrap(_l1ToL2Addresses[l1Req]);

    // L2 address is present in the request and L1 address is not.
    if (l2Req > 0 && l1Req == address(0)) {
        if (l1Mapping == address(0)) {
            // It's the first token of the collection to be bridged.
            return address(0);
        } else {
            // It's not the first token of the collection to be bridged,
            // and the collection tokens were only bridged L2->L1.
            return l1Mapping;
        }
    }

    // L2 address is present, and L1 address too.
    if (l2Req > 0 && l1Req > address(0)) {
        if (l1Mapping != l1Req) {
            revert InvalidCollectionL1Address();
        } else if (l2Mapping != l2Req) {
            revert InvalidCollectionL2Address();
        } else {
            // All addresses match, we don't need to deploy anything.
            return l1Mapping;
        }
    }

    revert ErrorVerifyingAddressMapping();
}
```
This function (_verifyRequestAddresses) is called whenever we withdraw tokens, where if the request came from L2 Bridge has a valid collectionL1 address (l1Req), we are doing checks that the matching of addresses is the same on both chains.
l2Req is the NFT collection we withdrew from on L2, and it should be a valid NFT collection address
l1Req is the l2tol1_addresses on L2 where if the collection has matching on L2 it will use that address when bridging tokens from L2 to L1.

bridge.cairo#L274
```cairo
let collectionl1 = self.l2tol1addresses.read(collection_l2);
```
So if the NFT collection has an L1<->L2 matching on L2 we will do a check that ensures the NFT collection L1 and L2 addresses on L2Bridge are the same in L1Bridge.
```solidity
if (l2Req > 0 && l1Req > address(0)) {
    if (l1Mapping != l1Req) {
        revert InvalidCollectionL1Address();
    } else if (l2Mapping != l2Req) {
        revert InvalidCollectionL2Address();
    } else {
        // All addresses match, we don't need to deploy anything.
        return l1Mapping;
    }
}
```
The problem is that setting l1<->l2 addresses on the L2Bridge doesn't mean that that value is always set on L1Bridge.

We are only setting l1<->l2 on the chain we are withdrawing from, so when bridging from L1 to L2. L2Bridge will set the matching between collections but L1 will not set that matching. So if we tried to withdraw from L2 to L1 the withdrawing will revert as it will compare a collection address with the address zero.

## Proof of Concept

Add the following test function function in apps/blockchain/ethereum/test/Bridge.t.sol.
```solidity
function testauditorcollectionmatchingone_chain() public {
    // alice deposit token 0 and 9 of collection erc721C1 to bridge
    test_depositTokenERC721();

    // Build the request and compute it's "would be" message hash.
    felt252 header = Protocol.requestHeaderV1(CollectionType.ERC721, false, false);

    // Build Request on L2
    Request memory req = buildRequestDeploy(header, 9, bob);
    req.collectionL1 = address(erc721C1);
    uint256[] memory reqSerialized = Protocol.requestSerialize(req);
    bytes32 msgHash = computeMessageHashFromL2(reqSerialized);

    // The message must be simulated to come from starknet verifier contract
    // on L1 and pushed to starknet core.
    uint256[] memory hashes = new uint256[](1);
    hashes[0] = uint256(msgHash);
    IStarknetMessagingLocal(snCore).addMessageHashesFromL2(hashes);

    // Withdrawing tokens will revert as There is no matching on L1
    address collection = IStarklane(bridge).withdrawTokens(reqSerialized);
}
```
In the cmd write the following command.
```shell
forge test --mt testauditorcollectionmatchingone_chain -vv
```
Output
The function will revert with an error message InvalidCollectionL1Address()
```powershell
Ran 1 test for test/Bridge.t.sol:BridgeTest
[FAIL. Reason: InvalidCollectionL1Address()] testauditorcollectionmatchingone_chain() (gas: 648188)
Suite result: FAILED. 0 passed; 1 failed; 0 skipped; finished in 5.71ms (1.77ms CPU time)
```

## Recommendation

Do not check the correct l1<->l2 matching on L1 and L2 if the L1 has no matching yet.
```diff
diff --git a/apps/blockchain/ethereum/src/token/CollectionManager.sol b/apps/blockchain/ethereum/src/token/CollectionManager.sol
index ec9429a..f790f70 100644
--- a/apps/blockchain/ethereum/src/token/CollectionManager.sol
+++ b/apps/blockchain/ethereum/src/token/CollectionManager.sol
@@ -113,7 +113,6 @@ contract CollectionManager {
         snaddress collectionL2Req
     )
         internal
         view
         returns (address)
     {
         address l1Req = collectionL1Req;
@@ -133,6 +132,13 @@ contract CollectionManager {
             }
         }
        // L2 is present, L1 address too, and there is no mapping
        if (l2Req > 0 && l1Req > address(0) && l1Mapping == address(0) && l2Mapping == 0) {
            _l1ToL2Addresses[l1Req] = collectionL2Req;
            _l2ToL1Addresses[collectionL2Req] = l1Req;
            return l1Req;
        }
        // L2 address is present, and L1 address too.
         if (l2Req > 0 && l1Req > address(0)) {
             if (l1Mapping != l1Req) {
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability occurs in the cross‑chain NFT bridge when a collection has been paired on the destination chain but the corresponding pairing has not yet been recorded on the source chain. The bridge’s internal function that validates address mappings (_verifyRequestAddresses) requires that both the L1 and L2 collection addresses be present and match the stored mappings on each side. When a user bridges an NFT from L1 to L2, the L2 bridge records the L1↔L2 relationship only on the L2 side. The L1 side does not create the reciprocal entry. Consequently, if the user later attempts to bridge the same NFT back from L2 to L1, the verification logic finds a non‑zero L2 address together with a non‑zero L1 address supplied in the request, but the stored L1 mapping on the L2 bridge is still zero. The function then triggers the revert InvalidCollectionL1Address(). This mismatch is the root cause: the bridge assumes that a mapping exists on both chains at the time of any withdrawal, which is not true for the first reverse transfer after an initial forward transfer.

An attacker or any user can exploit this by simply performing a normal forward bridge (L1→L2) and then attempting the reverse operation. The transaction will revert, leaving the NFT locked on the L2 side. From the user’s perspective the expected outcome – the NFT appearing in their wallet on L1 – does not happen; instead the transaction fails with an error and the balance shown on the UI remains unchanged, creating the impression that the bridge “eats” the token. The impact is a denial‑of‑service condition for the affected collection: funds (the NFT) become inaccessible until the mapping is manually corrected or the contract is upgraded. This issue affects all participants who rely on the bridge to move NFTs between the two chains, as well as the protocol’s reputation for reliable cross‑chain transfers.

The problem was discovered during a security audit when a test case deliberately withdrew a token after a forward bridge and observed the InvalidCollectionL1Address revert. The bug is subtle because the bridge correctly deploys or uses a collection address when moving from L1 to L2, so the forward direction appears to work, masking the asymmetry that only manifests on the reverse path.

To remediate, the verification logic should be relaxed to allow a missing mapping on the source side and automatically create the reciprocal entry when both addresses are supplied, or the bridge should skip the strict equality check when the stored mapping is zero. In essence, the contract must treat the address pair as a bidirectional relationship that can be established from either side, ensuring that the first reverse transfer does not fail due to an absent entry. Implementing this change restores the intended business logic that an NFT can be freely moved back and forth without unexpected reverts, preserving user balances and protocol integrity.
