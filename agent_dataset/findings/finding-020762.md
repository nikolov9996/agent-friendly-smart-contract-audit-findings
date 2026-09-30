---
id: 20762
severity: "High"
---

# Absence of restrictions on the sender of the `twTAP.claimRewards`

## Description

The function `twTAP.claimRewards()` is utilized to claim the reward distributed to the position identified by `_tokenId`.

```solidity
function claimRewards(uint256 _tokenId, address _to)
    external
    nonReentrant
    whenNotPaused
    returns (uint256[] memory amounts_)
{
    _requireClaimPermission(_to, _tokenId);
    amounts_ = _claimRewards(_tokenId, _to);
}
```

This function can be triggered by anyone, provided that the receiver of the claimed reward `_to` is either the owner of the position or an address approved by the position’s owner.

In the function `TapTokenReceiver._claimTwpTapRewardsReceiver()`, the `twTAP.claimRewards()` function is invoked at [line 156](https://github.com/Tapioca-DAO/tap-token/blob/20a83b1d2d5577653610a6c3879dff9df4968345/contracts/tokens/TapTokenReceiver.sol#L156) to calculate the reward assigned to `_tokenId` and claim the reward to this contract before transferring it to the receiver on another chain. To achieve this, the position’s owner must first approve this contract to access the position before executing the function.

```solidity
function _claimTwpTapRewardsReceiver(bytes memory _data) internal virtual twTapExists {
    ClaimTwTapRewardsMsg memory claimTwTapRewardsMsg_ = TapTokenCodec.decodeClaimTwTapRewardsMsg(_data);
    uint256[] memory claimedAmount_ = twTap.claimRewards(claimTwTapRewardsMsg_.tokenId, address(this));

    ...
}
```

However, between the call to grant approval to the contract and the execution of the `_claimTwpTapRewardsReceiver()` function, an attacker can insert a transaction calling `twTAP.claimRewards(_tokenId, TapTokenReceiver)`. By doing so, the rewards will be claimed to the `TapTokenReceiver` contract before the `_claimTwpTapRewardsReceiver()` function is invoked. Consequently, the return value of `claimedAmount_ = twTap.claimRewards(claimTwTapRewardsMsg_.tokenId, address(this))` within the function will be `0` for all elements, resulting in no rewards being claimed for the receiver. As a result, the reward tokens will become trapped in the contract.

In the event that the sender utilizes multiple LayerZero composed messages containing two messages:

  * Permit message: to approve permission of `_tokenId` to the `TapTokenReceiver` contract.
  * Claim reward message: to trigger the `_claimTwpTapRewardsReceiver()` function and claim the reward.

The attacker cannot insert any `twTAP.claimRewards()` between these two messages, as they are executed within the same transaction on the destination chain. However, the permit message can be triggered by anyone, not just the contract `TapTokenReceiver`. The attacker can thus trigger the permit message on the destination chain and subsequently call the `twTAP.claimRewards()` function before the `_claimTwpTapRewardsReceiver()` message is delivered on the destination chain.

## Proof of Concept

no poc

## Recommendation

Consider updating the function `twTAP.claimRewards()` as depicted below to impose restrictions on who can invoke this function:

```solidity
function claimRewards(uint256 _tokenId, address _to)
    external
    nonReentrant
    whenNotPaused
    returns (uint256[] memory amounts_)
{
    _requireClaimPermission(msg.sender, _tokenId);
    _requireClaimPermission(_to, _tokenId);
    amounts_ = _claimRewards(_tokenId, _to);
}
```

Just as reference, the proposed mitigation will not work, because in this context `msg.sender == _to`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the reward‑claiming function of the twTAP contract. The function claimRewards(uint256 _tokenId, address _to) is intended to transfer the reward accrued by a specific position to a designated recipient. However, the function only verifies that the destination address _to is either the owner of the position or an address approved by the owner; it does not restrict who may invoke the function. Because the caller (msg.sender) is not checked, any external account can trigger the claim on behalf of any approved recipient. This missing access‑control creates a race condition: an attacker can observe a legitimate user’s workflow that first grants approval to the TapTokenReceiver contract and then expects the contract to call claimRewards on the destination chain. Between the approval transaction and the internal call that actually pulls the reward, the attacker can submit a separate transaction calling twTAP.claimRewards(_tokenId, TapTokenReceiver). By doing so the attacker forces the reward to be transferred to the TapTokenReceiver contract before the contract’s internal logic runs. When the contract later executes its internal _claimTwpTapRewardsReceiver function, the call to twTap.claimRewards returns zero for all reward amounts because the rewards have already been drained, leaving the intended receiver with no tokens and causing the reward tokens to become permanently locked in the contract. The issue manifests only when the permission‑granting step and the reward‑claiming step are executed in separate transactions, which is the case for cross‑chain messages that are composed of a permit message followed by a claim message. From a user’s perspective the UI will show that the reward balance is zero after the approval, even though the protocol reports that rewards were distributed. The impact is high because funds can be permanently lost for any user who relies on the cross‑chain claim flow, and the problem is difficult to notice because the contract does not emit an explicit error; it simply returns zero amounts. The flaw was discovered during a security audit that examined the interaction between the TapTokenReceiver contract and the twTAP reward contract, revealing that the only guard in place is a check on the recipient address, not on the caller. The root cause is an absent sender restriction, which allows front‑running attacks. To remediate the issue the claimRewards function should enforce that the caller is authorized to claim on behalf of the position, for example by requiring that msg.sender has permission for the tokenId in addition to the _to address, or by redesigning the flow to use a pull‑based pattern where the contract itself initiates the claim after the approval is securely recorded. The proposed fix in the original report, which adds a _requireClaimPermission(msg.sender, _tokenId) check, is insufficient because in the intended usage msg.sender equals _to, so the same vulnerability persists. A robust solution must either bind the claim to the approved contract or employ a nonce/commit‑reveal scheme to prevent front‑running, ensuring that rewards cannot be intercepted and that users receive the amounts they expect.
