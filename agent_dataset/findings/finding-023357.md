---
id: 23357
severity: "High"
---

# Same wallet can be added multiple times to an investor, artificially increasing their wallet count causing adding new wallets to revert

## Description

Description: GlobalRegistryService::_updateInvestor calls _addWallet when the wallet being added is al-
ready registered to this investor:
```solidity
for (uint8 i = 0; i < walletAddresses.length; i++) {
    // @audit if it is a wallet and it doesn't belong to this investor, revert
    if (isWallet(walletAddresses[i]) && !CommonUtils.isEqualString(getInvestor(walletAddresses[i]),
    id)) {
        revert WalletBelongsToAnotherInvestor();
    }
    // @audit otherwise add it - even if it is a wallet that already belongs to this investor!
    else {
        _addWallet(walletAddresses[i], id);
    }
}
```
GlobalRegistryService::_addWallet in turn increments the investor's walletCount and reverts once the max
are reached:
```solidity
function _addWallet(address walletAddress, string memory id) internal addressNotZero(walletAddress)
returns (bool) {
    if (investors[id].walletCount >= MAX_WALLETS_PER_INVESTOR) {
        revert MaxWalletsReached();
    }
    address sender = _msgSender();
    investorsWallets[walletAddress] = Wallet(id, sender);
    investors[id].walletCount++;
    emit GlobalWalletAdded(walletAddress, id, sender);
    return true;
}
```
Impact: An investor's wallet count can be artificially inflated when updating that investor's details especially via
GlobalRegistryService::updateInvestor which can be called with all of an investor's existing data and only
some modified fields. Once MAX_WALLETS_PER_INVESTOR is reached no further updates are possible.
There are also other impacts such as never being able to remove an investor since GlobalRegistrySer-
vice::removeWallet won't be able to decrement the investor's walletCount back to 0 hence removeInvestor
will always revert.

## Proof of Concept

First add this view function to GlobalRegistryService.sol:
```solidity
function walletCountByInvestor(string calldata investorId) public view returns (uint256) {
    return investors[investorId].walletCount;
}
```
Then add the PoC to global-registry-service.tests.ts:
```typescript
it('Bug - adding same wallet for same investor inflates wallet count', async function () {
    const [, investor] = await hre.ethers.getSigners();
    const { globalRegistryService } = await loadFixture(deployGRS);
    await globalRegistryService.updateInvestor(
        INVESTORS.INVESTOR_ID.INVESTOR_ID_1,
        INVESTORS.INVESTOR_ID.INVESTOR_COLLISION_HASH_1,
        US,
        [investor],
        6,
        [1, 2, 4],
        [1, 1, 1],
        [0, 0, 0],
    );
    await globalRegistryService.updateInvestor(
        INVESTORS.INVESTOR_ID.INVESTOR_ID_1,
        INVESTORS.INVESTOR_ID.INVESTOR_COLLISION_HASH_1,
        US,
        [investor],
        [1, 2, 4],
        [1, 1, 1],
        [0, 0, 0],
    );
    expect(await
        globalRegistryService.walletCountByInvestor(INVESTORS.INVESTOR_ID.INVESTOR_ID_1)).to.equal(2);
});
```
Run with `npx hardhat test --grep "adding same wallet for same investor inflates wallet count"`.

## Recommendation

Recommended Mitigation: In GlobalRegistryService::_updateInvestor if the wallet being added is a wallet
and already belongs to the same investor, don't do anything. Here is a more efficient implementation of _up-
dateInvestor that avoids duplicate work done by the isWallet and isInvestor functions while also fixing this
bug:
```solidity
function _updateInvestor(string calldata id, address[] memory walletAddresses) internal returns (bool) {
    // revert if max wallet would be breached
    uint256 walletAddressesLen = walletAddresses.length;
    if (walletAddressesLen > MAX_WALLETS_PER_INVESTOR) {
        revert TooManyWallets();
    }
    // register investor if they don't already exist
    if (!isInvestor(id)) {
        _registerInvestor(id);
    }
    for (uint8 i; i < walletAddressesLen; i++) {
        address newWallet = walletAddresses[i];
        // is the wallet already registered to an investor?
        string memory walletExistingInvestor = getInvestor(newWallet);
        // if not then add it
        if(!isInvestor(walletExistingInvestor)) {
            _addWallet(newWallet, id);
        }
        // otherwise revert if it is registered to another investor
        else if(!CommonUtils.isEqualString(walletExistingInvestor, id)) {
            revert WalletBelongsToAnotherInvestor();
        }
        // if it is already registered to this investor, do nothing
    }
    return true;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect handling of duplicate wallet registrations in the GlobalRegistryService contract. When the public updateInvestor function processes a list of wallet addresses, it invokes an internal _addWallet routine for every entry that passes a basic ownership test. The test only rejects wallets belonging to a different investor, but it does not exclude wallets that are already associated with the same investor. Consequently, _addWallet is called even for duplicate addresses, and each call blindly increments the investor's walletCount state variable. Because the counter is increased without checking for existing membership, an attacker or even an honest user can repeatedly submit the same wallet address and artificially inflate the count. Once the inflated count reaches the hard‑coded MAX_WALLETS_PER_INVESTOR limit, any further attempt to add a new wallet triggers a MaxWalletsReached revert, effectively locking the investor out of adding new wallets. The bug also interferes with removal logic: removeWallet decrements the counter, but if the counter has been over‑inflated it may never reach zero, causing removeInvestor to revert and preventing the complete deletion of an investor. The issue manifests to users as a mismatch between the displayed list of wallets (which remains unchanged) and the reported wallet count, leading to unexpected errors when trying to add or remove wallets. It was discovered during a security audit that included a targeted test case adding the same wallet twice and observing the counter increase. The problem is subtle because the contract does not emit an explicit error for duplicate additions; the symptom only appears later when the maximum limit is hit. The vulnerability belongs to the class of state‑inconsistent accounting bugs where counters are not kept in sync with the underlying data structures. To remediate, the updateInvestor logic must include a guard that skips the addition when the wallet is already registered to the same investor, or otherwise ensure that the walletCount is only incremented for truly new wallets. This change restores the invariant that walletCount accurately reflects the number of distinct wallet addresses associated with an investor, preventing denial‑of‑service scenarios and preserving the ability to manage investor records safely.
