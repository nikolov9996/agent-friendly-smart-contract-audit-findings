---
id: 8619
severity: "High"
---

# Users Can Use Flashloan to Increase Voting Power of Expired Positions and Execute Proposal for Their Benefits

## Description

If we assume the Medium-01 from the report is fixed in the `increaseAndStake()` function which allows users to add the amount to their stake without updating the lock duration then the below scenario might be executable:
• Assume Alice’s `lockUntil` reached the current `block.timestamp`.
• Alice got a huge flashloan of GUAN token (can get another token as flashloan and then swap it to GUAN) and called the `increaseAndStake()` function with the flashloan amount.
• If we assume the Medium-01 issue is fixed then the transaction will be executed without reverting since Alice increased the stake amount only.
• The `veGUAN` core logic allows the stakes to have voting power depending on their stake amount even if the lock duration expired, this is clearly shown in the function below:
```solidity
function _calculateVotingPower(
    UD60x18 votingPowerCurveAFactorX18,
    UD60x18 remainingLockDurationX18,
    UD60x18 positionStakeX18
)
internal
pure
returns (uint256 scalingFactor, uint256 votingPower)
{
    // calculate the lock multiplier as explained in the function's natspec
    UD60x18 scalingFactorX18 = votingPowerCurveAFactorX18.mul(remainingLockDurationX18).add(UNIT); // @audit 1e18 get added even if the calc = 0
    // return the scaling factor and voting power
    scalingFactor = scalingFactorX18.intoUint256();
    votingPower = positionStakeX18.mul(scalingFactorX18).intoUint256();
}
```
• This way Alice can have huge voting power due to her flashloan amount and she can execute a proposal and vote for it in one transaction and then unstake her GUAN token (the tx won’t revert since `block.timestamp == lockUntil`:

```solidity
function unstake(uint256 tokenId, uint256 amount) external onlyTokenOwner(tokenId) {
    // load veGUAN storage slot
    VeGuanStorage storage $ = _getVeGuanStorage();
    // load the lock data storage pointer
    LockedPositionData storage lockedPosition = $.lockedPositions[tokenId];
    // revert if the position is still locked
    if (block.timestamp < lockedPosition.lockedUntil) {
        revert PositionIsLocked();
    }
    // deduct the unstake amount from the locked position's state, if there isn't enough stake in the position the
    // call will revert with an underflow
    lockedPosition.stake -= amount;
    // transfer the lp tokens to the `msg.sender`
    IERC20($.lpToken).safeTransfer(msg.sender, amount);
    // cache the veGUAN's voting power
    (, uint256 votingPower) = getVotingPowerOf(tokenId);
    // emit an event
    emit LogUnstake(msg.sender, tokenId, lockedPosition.stake, votingPower);
}
```
This issue could potentially occur based on the current small codebase. However, the GUAN documentation states that proposals are reviewed by the council, which may prevent this issue from being executed.

A malicious user can execute a flashloan attack to gain huge vote power to execute a proposal.

## Proof of Concept

no poc

## Recommendation

If the check changed from the `unstake()` function then the attack can be prevented:
```solidity
if (block.timestamp <= lockedPosition.lockedUntil)
```
Another check can be added in `increaseAndStake()` which prevents increasing stake amount for expired positions.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the governance token contract where a user can increase the stake of a voting position that has already passed its lock expiration and still obtain voting power. The root cause is that the internal voting‑power calculation multiplies the position stake by a scaling factor that always adds a base unit (1e18) even when the remaining lock duration is zero, and the increaseAndStake function does not verify that the lock period is still active before allowing additional tokens to be added. An attacker can obtain a large amount of the underlying token through a flash‑loan, call increaseAndStake on an expired position, and instantly acquire a huge voting weight because the formula treats the expired lock as if it still contributes a non‑zero multiplier. With this inflated voting power the attacker can submit and approve a governance proposal in the same transaction, then immediately call unstake to withdraw the flash‑loaned tokens because the unstake function only reverts when block.timestamp is less than the lock expiry, not when it is equal. The attack therefore succeeds exactly at the moment the lock has just expired, allowing the transaction to complete without any revert. The impact is that a malicious actor can manipulate the protocol’s governance, passing proposals that benefit themselves or harm other participants, while the protocol appears to have behaved normally from a user‑interface perspective – votes are counted, proposals are approved, and token balances seem unchanged until the flash‑loan is repaid. This issue was discovered during a security audit that examined the logic of increaseAndStake and the voting‑power formula, noting that the lock‑duration check was missing and that the scaling factor adds a constant term regardless of lock status. The bug is subtle because the contract still returns a non‑zero voting power for expired positions, which may be assumed to be legitimate by users and auditors who focus on stake amount alone. To remediate, the contract should reject any increaseAndStake calls on positions whose lock has expired, and the unstake function should require block.timestamp to be strictly greater than the lock expiry (or use a <= check) before allowing withdrawals, thereby ensuring that no voting power can be generated from an expired lock. Conceptually, this is a class of governance‑power inflation bugs where token‑locking mechanisms fail to enforce lock‑duration constraints, leading to vote‑weight manipulation and potential governance takeover.
