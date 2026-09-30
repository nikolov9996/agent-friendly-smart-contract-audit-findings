---
id: 23213
severity: "High"
---

# InfernalRiftBelow.thresholdCross

## Description

InfernalRiftBelow.thresholdCross verify the wrong msg.sender, thresholdCross will fail to be called, resulting in the loss of user assets.
thresholdCross determines whether msg.sender is expectedAliasedSender:
```solidity
address expectedAliasedSender = address(uint160(INFERNAL_RIFT_ABOVE) +
uint160(0x1111000000000000000000000000000000001111));
// Ensure the msg.sender is the aliased address of {InfernalRiftAbove}
if (msg.sender != expectedAliasedSender) {
    revert CrossChainSenderIsNotRiftAbove();
}
```
but in fact the function caller should be RELAYER_ADDRESS, In sudoswap, crossTheThreshold check whether msg.sender is RELAYER_ADDRESS: https://github.com/sudoswap/InfernalRift/blob/7696827b3221929b3fa563692bd4c5d73b20528e/src/InfernalRiftBelow.sol#L56
L1 across chain message through the PORTAL.depositTransaction, rather than L1_CROSS_DOMAIN_MESSENGER.
To avoid confusion, use in L1 should all L1_CROSS_DOMAIN_MESSENGER.sendMessage to send messages across the chain, avoid the use of low level PORTAL.depositTransaction function.
```solidity
function crossTheThreshold(ThresholdCrossParams memory params) external payable {
    // Send package off to the portal
    PORTAL.depositTransaction{value: msg.value}(
        INFERNAL_RIFT_BELOW,
        0,
        params.gasLimit,
        false,
        abi.encodeCall(InfernalRiftBelow.thresholdCross, (package,
        params.recipient))
    );
    emit BridgeStarted(address(INFERNAL_RIFT_BELOW), package, params.recipient);
}
```
When transferring nft across chains, thresholdCross cannot be called in L2, resulting in loss of user assets.

## Proof of Concept

no poc

## Recommendation

```solidity
// Validate caller is cross-chain
if (msg.sender != RELAYER_ADDRESS) { //or L2_CROSS_DOMAIN_MESSENGER
    revert NotCrossDomainMessenger();
}
// Validate caller comes from {InfernalRiftBelow}
if (ICrossDomainMessenger(msg.sender).xDomainMessageSender() != InfernalRiftAbove) {
    revert CrossChainSenderIsNotRiftBelow();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the cross‑chain bridge function thresholdCross of the InfernalRiftBelow contract. The function attempts to verify that the caller (msg.sender) matches an address that is calculated by aliasing the address of the InfernalRiftAbove contract with a fixed constant. In reality, the bridge architecture expects the caller to be the designated RELAYER_ADDRESS, which is the entity that forwards cross‑domain messages from L1 to L2. Because the verification logic checks against the wrong aliased address, any legitimate call originating from the relayer fails the if‑statement and triggers the CrossChainSenderIsNotRiftAbove revert. This mismatch occurs when the higher‑level function crossTheThreshold uses the low‑level PORTAL.depositTransaction to forward the message instead of the standard L1_CROSS_DOMAIN_MESSENGER, causing the L2 side to receive a call from an unexpected sender. When a user initiates an NFT transfer across chains, the bridge emits a BridgeStarted event and deposits the transaction, but the subsequent call to thresholdCross on L2 reverts, leaving the NFT locked in the bridge contract and never arriving at the intended recipient. From the user’s perspective the symptom is a missing NFT or a zero balance after the bridge operation, contrary to the expectation that the asset would appear on the destination chain. The issue was discovered during a security audit by Sherlock, who identified the logical flaw in the sender validation. It is hard to notice because the transaction appears to be accepted on L1, no explicit error is shown in the UI, and the assets simply disappear from the user’s view. The root cause is an incorrect authentication check – the contract validates against an aliased address rather than the authorized relayer or cross‑domain messenger. To remediate, the contract should validate that msg.sender equals the RELAYER_ADDRESS (or the appropriate L2 cross‑domain messenger) and additionally confirm that the xDomainMessageSender reported by the messenger matches the InfernalRiftAbove contract. This change aligns the authentication with the intended bridge design, prevents the revert, and ensures that assets are correctly transferred across chains without loss.
