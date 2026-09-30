---
id: 10799
severity: "High"
---

# executeCallback call causes that ownership cannot be updated on the base chain

## Description

When Beacon.triggerOwnershipUpdate() is called, the new owners of the tokens are read from the target chain, and Beacon._updateOwnership() is executed on the source chain to update the ownership. When this is executed on the NFT's native chain, shadowAddress is the address of the NFT contract, not the NFTShadow contract. As such, when _shadow.executeCallback(guid) is called at the end of the function, the transaction will revert, as the NFT contract does not have the executeCallback function.
```solidity
function _updateOwnership(bytes calldata _message, bytes32 guid) internal {
    (
        address shadowAddress,
        address[] memory staleOwners,
        address[] memory newOwners,
        uint256[] memory tokenIds
    ) = abi.decode(_message, (address, address[], address[], uint256[]));
    // ...
    INFTShadow _shadow = INFTShadow(shadowAddress);
    // ...
    _shadow.executeCallback(guid);
}
```
As a result, the ownership cannot be updated on the native chain.

## Proof of Concept

No poc.

## Recommendation

```solidity
_shadow.executeCallback(guid);
```
```solidity
if (!isNative) _shadow.executeCallback(guid);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the Beacon contract’s internal function that updates token ownership across chains. When Beacon.triggerOwnershipUpdate() is invoked, a message containing the address of the shadow contract, stale owners, new owners and token identifiers is decoded and the function _updateOwnership processes it. On a non‑native (target) chain the shadowAddress correctly points to an NFTShadow contract that implements the executeCallback(guid) function, allowing the callback to complete and the ownership state to be persisted. However, when the same logic runs on the NFT’s native chain, the shadowAddress resolves to the NFT contract itself, which does not implement executeCallback. Consequently the call _shadow.executeCallback(guid) reverts with a missing function selector error. Because the revert occurs after the ownership data has been prepared but before it is committed, the ownership update never finalises on the native chain. The root cause is the unconditional invocation of the callback without verifying that the current chain is a shadow (non‑native) environment, effectively treating the NFT contract as if it were an NFTShadow contract. An attacker does not need to actively exploit the bug; any legitimate attempt to trigger an ownership transfer on the native chain will fail, causing the transaction to revert and leaving the token’s ownership unchanged. This results in a denial‑of‑service condition for token holders: users attempting to transfer, sell or otherwise move their NFTs receive a transaction failure, see no change in balance, and may interpret the behaviour as a loss of funds or a broken protocol. The issue was discovered during a manual security audit that examined cross‑chain ownership flows and identified that the callback was always executed regardless of chain context. It is subtle because the same code path works correctly on remote chains, so tests that only cover those paths may not reveal the problem. To remediate the issue the contract should either (1) conditionally skip the executeCallback call when operating on the native chain, for example by checking an isNative flag before invoking the function, or (2) ensure that the address stored in shadowAddress always points to a contract that implements the required interface, possibly by storing separate addresses for native and shadow contexts. Either approach prevents the revert and restores the ability for ownership updates to succeed on the native chain, thereby preserving the intended cross‑chain accounting guarantees.
