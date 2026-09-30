---
id: 6178
severity: "Critical"
---

# Permanent failure to bridge wrapped ERC721 using Bridge::sendERC721UsingNative function

## Description

The sendERC721UsingNative function of Bridge.sol bridges ERC721 NFTs between multiple supported networks using Layerzero's message bridge. This function helps to bridge both the original asset (the unwrapped asset) and the wrapped asset. However, due to an implementation error, this function works only for the original asset and locks the wrapped asset on the bridged chain, unable to bridge it. This failure to bridge would permanently lock the original NFT in the source bridge contract.

## Proof of Concept

The vulnerability is demonstrated using the following foundry test code. To run it, copy it to the test file and run foundry test --mt test_e2e
```solidity
function test_e2e() external {
vm.selectFork(forkIds[ETH]);
deal(user, 100 ether);
uint256[] memory tokenIds = new uint256[](2);
tokenIds[0] = 1;
tokenIds[1] = 2;
vm.startPrank(user);
testNft.setApprovalForAll(address(bridge[ETH]), true);
vm.recordLogs();
bridge[ETH].sendERC721UsingNative{value: 1 ether}(137, address(testNft), tokenIds);
vm.stopPrank();
lzHelper.help(lzEndpoint, forkIds[POLY],
vm.getRecordedLogs());
vm.selectFork(forkIds[POLY]);
deal(user, 100 ether);
address wrappedNft = bridge[POLY].getWERC721FromOriginERC721Address(address(testNft)).wrappedAddress;
vm.prank(admin);
bridge[POLY].setWrapperRoyalty(address(wrappedNft), treasure, 1, 1);
vm.startPrank(user);
ERC721(wrappedNft).setApprovalForAll(address(bridge[POLY]), true);
vm.recordLogs();
bridge[POLY].sendERC721UsingNative{value: 1 ether}(137, address(wrappedNft), tokenIds);
vm.stopPrank();
lzHelper.help(lzEndpoint, forkIds[ETH],
vm.getRecordedLogs());
}
```
While trying to bridge from Polygon to ETH using both the originalNft and wrappedNft addresses the following error occurred:
Bridge::sendERC721UsingNative{value: 1000000000000000000}(137, WERC721: [0x7731e5F9c2c4cD867510F83b54A3B93A9Ce16D5b], [1, 2])
[246] ReentrancyGuard::_nonReentrantBefore()
[980] Bridge::getEvmChainSettings(137, 0)
<unknown>
[981] Bridge::getEvmChainSettings(137, 0)
<unknown>
[981] Bridge::getEvmChainSettings(137, 0)
<unknown>
[982] Bridge::getEvmChainSettings(137, 1)
<unknown>
[603] Bridge::getWERC721FromOriginERC721Address(0xe0dBab467aaea6B2e33EbaD8fdAe07235242D566)
<unknown>
[0] TestNft::tokenURI(1) [staticcall]
[Stop]
[Revert] EvmError: Revert
[Revert] Contract 0xe0dBab467aaea6B2e33EbaD8fdAe07235242D566 does not exist on active fork with id `1` But exists on non active forks: `[0]`
Further analysis shows that the function reverts as it tries to access the token URI from the original asset on the bridged chain rather than the wrapped asset.

## Recommendation

To fix the above mentioned error, the two internal functions _getPayload and _getPayloadMessage has to be updated as follows:
```solidity
function getPayload(
uint256 evmChainId,
address ERC721Address_,
uint256[] memory tokensIds_
) internal view returns (IBaseAdapter.MessageSend memory) {
// ...
/// @dev if ERC721Address not wrapped, use the ERC721 address
address currChainAddress_ = ERC721Wrapped.originAddress == address(0)
? ERC721Address
: ERC721Wrapped.wrappedAddress;
address originERC721Address = ERC721Wrapped.originAddress == address(0)
? ERC721Address
: ERC721Wrapped.originAddress;
// ...
return getPayloadMessage(
tokensIds_,
currChainAddress_,
originERC721Address_,
originEvmChainId_,
targetEvmChainSettings
);
}
function getPayloadMessage(
uint256[] memory tokensIds_,
address currChainAddress_,
address originERC721Address_,
uint256 originEvmChainId_,
IBridge.EvmChainSettings memory evmChainSettings_
) internal view returns (IBaseAdapter.MessageSend memory) {
IERC721Metadata metadata = IERC721Metadata(currChainAddress);
// ...
uint256 royaltyPercentage = getRoyaltyPercentage(currChainAddress_);
IBridge.ERC721Token memory tokenData = IBridge.ERC721Token({
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the Bridge contract function that bridges ERC721 tokens across chains using LayerZero. The function is intended to handle both the original (unwrapped) NFT and its wrapped counterpart, but due to an implementation mistake the payload that is sent to the destination chain is built with the address of the original asset even when the caller supplies a wrapped ERC721 address. Consequently the bridge attempts to read metadata such as tokenURI from the original contract on the target chain, a contract that does not exist there. The call reverts, the transaction fails and the NFT remains locked inside the source bridge contract. This condition occurs whenever a user tries to bridge a wrapped ERC721 (WERC721) with Bridge::sendERC721UsingNative, regardless of the source or destination network, and it does not affect bridging of the native asset. The root cause is the incorrect selection of the current‑chain address and origin address inside the internal _getPayload and _getPayloadMessage helpers, which treat the wrapped token as if it were the original token. Exploitation is straightforward: a user initiates a bridge of a wrapped NFT, the transaction reverts, and the NFT is permanently unavailable on both chains because the bridge contract never releases it. From the user’s perspective the UI shows the NFT disappearing from their wallet, the balance becomes zero, and no receipt of the token appears on the destination chain, contrary to the expectation that the NFT would be transferred. The issue was discovered during a formal audit when a Foundry test reproduced a revert with a message indicating that the original contract does not exist on the active fork. The bug is subtle because the same function works for original NFTs, so the failure only appears for wrapped assets, making it easy to overlook. The problem belongs to the class of cross‑chain address‑mapping bugs that cause asset lock due to incorrect payload construction. The recommended remediation is to modify the payload generation logic so that when a wrapped ERC721 is supplied the bridge uses the wrapped address for the current chain and the stored origin address for the source chain, as shown in the provided code snippet. This change ensures that the correct contract is referenced on the destination chain, allowing the token metadata call to succeed and the NFT to be released, thereby restoring the intended bridging functionality.
