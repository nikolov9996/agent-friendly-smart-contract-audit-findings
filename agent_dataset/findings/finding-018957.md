---
id: 18957
severity: "Medium"
---

# Users can unfollow through `FollowNFT` contract when LensHub is paused by governance

## Description

When the `LensHub` contract has been paused by governance (`_state` set to `ProtocolState.Paused`), users should not be able unfollow profiles. This can be inferred as the `unfollow()` function has the `whenNotPaused` modifier:
```solidity
function unfollow(uint256 unfollowerProfileId, uint256[] calldata idsOfProfilesToUnfollow)
    external
    override
    whenNotPaused
```
However, in the `FollowNFT` contract, which is deployed for each profile that has followers, the `removeFollower()` and `burn()` functions do not check if the `LensHub` contract is paused:
```solidity
function removeFollower(uint256 followTokenId) external override {
    address followTokenOwner = ownerOf(followTokenId);
    if (followTokenOwner == msg.sender || isApprovedForAll(followTokenOwner, msg.sender)) {
        _unfollowIfHasFollower(followTokenId);
    } else {
        revert DoesNotHavePermissions();
    }
}
```
```solidity
function burn(uint256 followTokenId) public override {
    _unfollowIfHasFollower(followTokenId);
    super.burn(followTokenId);
}
```
As such, whenever the system has been paused by governance, users will still be able to unfollow profiles by wrapping their followNFT and then calling either `removeFollower()` or `burn()`.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import 'test/base/BaseTest.t.sol';

contract Unfollow_POC is BaseTest {
    address targetProfileOwner;
    uint256 targetProfileId;
    FollowNFT targetFollowNFT;

    address follower;
    uint256 followerProfileId;
    uint256 followTokenId;

    function setUp() public override {
        super.setUp();

        // Create profile for target
        targetProfileOwner = makeAddr("Target");
        targetProfileId = _createProfile(targetProfileOwner);

        // Create profile for follower
        follower = makeAddr("Follower");
        followerProfileId = _createProfile(follower);

        // Follower follows target
        vm.prank(follower);
        followTokenId = hub.follow(
            followerProfileId,
            _toUint256Array(targetProfileId),
            _toUint256Array(0),
            _toBytesArray('')
        )[0];
        targetFollowNFT = FollowNFT(hub.getProfile(targetProfileId).followNFT);
    }

    function testCanUnfollowWhilePaused() public {
        // Governance pauses system
        vm.prank(governance);
        hub.setState(Types.ProtocolState.Paused);
        assertEq(uint8(hub.getState()), uint8(Types.ProtocolState.Paused));

        // unfollow() reverts as system is paused
        vm.startPrank(follower);
        vm.expectRevert(Errors.Paused.selector);
        hub.unfollow(followerProfileId, _toUint256Array(targetProfileId));

        // However, follower can still unfollow through FollowNFT contract 
        targetFollowNFT.wrap(followTokenId);
        targetFollowNFT.removeFollower(followTokenId);        
        vm.stopPrank();

        // follower isn't following anymore
        assertFalse(targetFollowNFT.isFollowing(followerProfileId));
    }
}
```

## Recommendation

All `FollowNFT` contracts should check that the `LensHub` contract isn’t paused before allowing `removeFollower()` or `burn()` to be called. This can be achieved by doing the following:

1. Add a `whenNotPaused` modifier to `FollowNFT.sol`:
```solidity
modifier whenNotPaused() {
    if (ILensHub(HUB).getState() == Types.ProtocolState.Paused) {
        revert Errors.Paused();
    }
    _;
}
```
2. Use the modifier on `removeFollower()` and `burn()`:
```solidity
function removeFollower(uint256 followTokenId) external override whenNotPaused {
    // Some code here...
}
```
```solidity
function burn(uint256 followTokenId) public override whenNotPaused {
    // Some code here...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an inconsistencybetween the LensHub contract and the per‑profile FollowNFT contracts regarding the protocol pause state. LensHub defines a global pause flag (ProtocolState.Paused) and protects its public unfollow function with a whenNotPaused modifier, meaning that when governance pauses the system users should be unable to call unfollow. However, each profile that has followers is represented by a separate FollowNFT contract that implements its own removeFollower and burn functions. These functions invoke the internal unfollow logic but do not check the LensHub pause flag before executing. As a result, when the LensHub contract is paused, a follower can still call FollowNFT.removeFollower or FollowNFT.burn (for example by wrapping the follow NFT and invoking the function) and successfully remove the follow relationship. The root cause is the missing pause guard in the FollowNFT contract, creating a cross‑contract state mismatch where the pause enforcement is not enforced uniformly. An attacker or any regular follower can exploit this by simply calling the NFT contract directly, bypassing the hub’s pause check. The impact is that governance loses the ability to freeze follow‑related state changes, allowing users to alter follow relationships during a pause, which may be used to manipulate on‑chain metrics, disrupt expected protocol behavior, or undermine confidence in the pause mechanism. The issue manifests only when the LensHub contract is in the Paused state; under normal operation both paths work as intended. Affected parties include profile owners who expect their follower list to be immutable during a pause, followers who may unintentionally change their follow status, and the protocol itself because the pause is intended to be a safety valve. The flaw was discovered during a formal audit when the test suite demonstrated that hub.unfollow reverted with a pause error while FollowNFT.removeFollower succeeded, confirming the inconsistency. The problem can be hard to notice because the pause modifier is present on the hub function, leading developers to assume that all follow‑related actions are automatically blocked when the protocol is paused. To remediate, the FollowNFT contract should incorporate the same whenNotPaused guard used by LensHub, either by adding a modifier that queries the hub’s state or by routing all unfollow actions through the hub so that the pause check is applied centrally. This aligns the contract’s behavior with the intended business logic that no follow‑related state changes should occur while the protocol is paused, restoring the integrity of the pause mechanism and preventing unexpected unfollow actions during emergency shutdowns.
