---
id: 21355
severity: "High"
---

# Invalid validation allows users to unlock early

## Description

Invalid validation in the `setLockDuration` function allows users to greatly reduce their unlock time or even unlock instantly.

## Proof of Concept

When a user locks his tokens in the `LockManager.sol` contract, the `unlockTime` is calculated as `block.timestamp + lockDuration`.

```solidity
function _lock(
    address _tokenContract,
    uint256 _quantity,
    address _tokenOwner,
    address _lockRecipient
) private {
    ---SNIP---

    lockedToken.remainder = remainder;
    lockedToken.quantity += _quantity;
    lockedToken.lastLockTime = uint32(block.timestamp);
    lockedToken.unlockTime =
        uint32(block.timestamp) +
        uint32(_lockDuration);
```

The `lockDuration` is a variable that can be configured by a user in the `setLockDuration` function anytime, even during the lock period.

```solidity
function setLockDuration(uint256 _duration) external notPaused {
    if (_duration > configStorage.getUint(StorageKey.MaxLockDuration))
        revert MaximumLockDurationError();

    playerSettings[msg.sender].lockDuration = uint32(_duration);
    ---SNIP---
```

The problem arises when existing locks are updated to the new duration.

```solidity
// update any existing lock
uint256 configuredTokensLength = configuredTokenContracts.length;
for (uint256 i; i < configuredTokensLength; i++) {
    address tokenContract = configuredTokenContracts[i];
    if (lockedTokens[msg.sender][tokenContract].quantity > 0) {
        // check they are not setting lock time before current unlocktime
        if (
            uint32(block.timestamp) + uint32(_duration) <
            lockedTokens[msg.sender][tokenContract].unlockTime
        ) {
            revert LockDurationReducedError();
        }

        uint32 lastLockTime = lockedTokens[msg.sender][tokenContract]
            .lastLockTime;
        lockedTokens[msg.sender][tokenContract].unlockTime =
            lastLockTime +
            uint32(_duration);
    }
}

emit LockDuration(msg.sender, _duration);
```

There is an invalid check performed, comparing `block.timestamp + _duration` with the current `unlockTime`. However, in the end, the new `unlockTime` is set as `lastLockTime + _duration`. This allows a user to reduce their lock duration and unlock their tokens earlier than initially intended. Let’s consider this scenario:

* Alice creates a lock for 100 days at day 0, unlockTime = 0 + 100 = 100th day
* on the 50-th day she calls `setLockDuration(51 days)`
* the contract compares 50 + 51 > 100 and sets unlockTime = 0 + 51 = 51th day

In this way, Alice can reduce her lock duration while still receiving bonuses as if she had a 100-day lock.

Check this coded POC for `SpeedRun.t.sol`

```solidity
function test_Early() public {
    uint256 lockAmount = 100e18;

    console.log("Beginning run()");
    deployContracts();

    // register me
    amp.register(MunchablesCommonLib.Realm(3), address(0));
    logSnuggery("Initial snuggery");

    // lock tokens for 86400 seconds
    lm.lock{value: lockAmount}(address(0), lockAmount);
    // 10000 seconds pass, use multiple setDurations to unlock instantly
    vm.warp(10000);
    lm.setLockDuration(76401);
    lm.setLockDuration(66402);
    lm.setLockDuration(56403);
    lm.setLockDuration(46404);
    lm.setLockDuration(36405);
    lm.setLockDuration(26406);
    lm.setLockDuration(16407);
    lm.setLockDuration(6408);
    lm.unlock(address(0), lockAmount);
}
```

In this test case user locked tokens for 86400 seconds and managed to unlock them after only 10000 seconds. This hack enables attacker to receive multiple NFT drops with `nftOverlord.addReveal` compared to honest users.

## Recommendation

```solidity
uint32 lastLockTime = lockedTokens[msg.sender][tokenContract]
if (
    lastLockTime + uint32(_duration) <
    lockedTokens[msg.sender][tokenContract].unlockTime
) {
    revert LockDurationReducedError();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect validation of lock‑duration updates in the setLockDuration function of the LockManager contract. The contract stores for each user a lastLockTime and an unlockTime that is initially calculated as block.timestamp plus the configured lock duration. When a user calls setLockDuration while a lock is already active, the code attempts to prevent shortening the lock by checking if block.timestamp plus the new duration is less than the current unlockTime. However, after this check the contract overwrites unlockTime with lastLockTime plus the new duration, completely ignoring the earlier comparison. Because lastLockTime is the timestamp of the original lock, a user can supply a smaller duration and cause unlockTime to be set to an earlier point, effectively reducing or even eliminating the remaining lock period. This flaw can be exploited by calling setLockDuration repeatedly with decreasing durations, as demonstrated in the SpeedRun test where a lock of 86400 seconds was unlocked after only 10000 seconds. The impact is that token holders can withdraw their tokens far earlier than promised while still receiving bonuses, NFT drops, or other rewards that are intended only for long‑term lockers. The issue occurs whenever a user has an active lock and the contract permits arbitrary updates to the lockDuration parameter during the lock period. All participants who rely on the lock‑time guarantee – including honest users, reward distributors, and the protocol’s economic model – are affected because the accounting assumptions about locked capital are broken. The problem was discovered during a formal audit when the test suite exercised the setLockDuration path and observed that the unlockTime could be manipulated. It is hard to notice because the initial check appears to enforce the correct invariant, giving a false sense of safety, while the later assignment silently defeats the check. To remediate, the contract should either forbid changing lockDuration after a lock is created or, if changes are allowed, compute the prospective new unlockTime as lastLockTime plus the new duration and reject any update that would make this new unlockTime earlier than the existing unlockTime. In other words, the validation must compare the same values that are later stored, ensuring that the lock period can never be shortened. This class of bug falls under improper time‑based constraint validation, where a security‑critical invariant is checked against one expression but enforced with a different one, leading to a logic error that permits premature release of locked assets.
