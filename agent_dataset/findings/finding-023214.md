---
id: 23214
severity: "High"
---

# InfernalRiftBelow.claimRoyalties

## Description

claimRoyalties used to accept the message on the L1, then execute ERC721Bridgable.claimRoyalties, but not the authentication callers, may result in the loss of the assets in the protocol.
claimRoyalties are used to accept cross-chain calls, but msg.sender is not validated:
```solidity
if (ICrossDomainMessenger(msg.sender).xDomainMessageSender() !=
INFERNAL_RIFT_ABOVE) {
    revert CrossChainSenderIsNotRiftAbove();
}
```
If msg.sender is a contract account implementing the ICrossDomainMessenger interface, the xDomainMessageSender function returns an address of INFERNAL_RIFT_ABOVE, which means that the claimRoyalties function can be invoked.
So anyone can call this function as long as he deploys a contract.
InfernalRiftBelow.claimRoyalties function will be called ERC721Bridgable.claimRoyalties, transfer NFTs from ERC721Bridgable contract, so any can transfer NFTs from ERC721Bridgable.
L1 Send message to L2:
```solidity
function claimRoyalties(address _collectionAddress, address _recipient, address[]
calldata _tokens, uint32 _gasLimit) external {
    .....
    ICrossDomainMessenger(L1_CROSS_DOMAIN_MESSENGER).sendMessage(
        INFERNAL_RIFT_BELOW,
        abi.encodeCall(
            IInfernalRiftBelow.claimRoyalties,
            (_collectionAddress, _recipient, _tokens)
        ),
        _gasLimit
    );
    emit RoyaltyClaimStarted(address(INFERNAL_RIFT_BELOW), _collectionAddress,
    _recipient, _tokens);
}
```
Anyone can steal NFT from the protocol.

## Proof of Concept

no poc

## Recommendation

```solidity
if (msg.sender != L2_CROSS_DOMAIN_MESSENGER) {
    revert NotCrossDomainMessenger();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the cross‑chain royalty claim function of the InfernalRiftBelow contract. The function is intended to accept messages from the L1 side, verify that the caller is the authorized cross‑domain messenger, and then forward the call to ERC721Bridgable.claimRoyalties which transfers NFTs to a recipient. The authentication logic is flawed because it only checks that the address returned by ICrossDomainMessenger(msg.sender).xDomainMessageSender() equals the expected L1 contract (INFERNAL_RIFT_ABOVE). An attacker can deploy a malicious contract that implements the ICrossDomainMessenger interface and makes its xDomainMessageSender function return the trusted address. Since the check does not validate that msg.sender itself is the known L2 messenger, the attacker’s contract passes the test and can invoke claimRoyalties directly. By calling the function, the attacker triggers ERC721Bridgable.claimRoyalties, causing NFTs held by the protocol to be transferred to an address of the attacker’s choosing. This can be done without any legitimate cross‑chain message, meaning the exploit is possible at any time the function is callable. The impact is the unauthorized loss of NFTs, effectively making user balances disappear and breaking the protocol’s accounting of royalty distributions. Users expect that royalties are claimed only by the designated bridge and that their assets remain safe; instead they may see their NFT balance drop to zero or receive no royalties. The issue was discovered during a security audit that examined the authentication flow and noticed that the contract relied on a mutable interface call rather than a fixed messenger address. The bug is subtle because the presence of a cross‑domain check gives a false sense of security, and the function otherwise behaves normally, so the unauthorized transfers may not generate obvious alerts. To remediate, the contract should enforce that only the known L2 cross‑domain messenger contract can call claimRoyalties, for example by checking msg.sender against a stored messenger address and reverting otherwise. This eliminates the ability for arbitrary contracts to spoof the xDomainMessageSender value and restores the intended trust boundary, preventing theft of NFTs and preserving the protocol’s financial integrity.
