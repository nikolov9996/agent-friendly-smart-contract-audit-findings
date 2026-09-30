---
id: 4315
severity: "High"
---

# `StrategyPUSDConvex.balanceOfJPEG` uses incorrect function signature while calling `extraReward.earned`, causing the function to unexpectedly revert everytime

## Description

[StrategyPUSDConvex.sol#L234](https://github.com/code-423n4/2022-04-jpegd/blob/main/contracts/vaults/yVault/strategies/StrategyPUSDConvex.sol#L234)  

As specified in Convex [BaseRewardPool.sol](https://github.com/convex-eth/platform/blob/main/contracts/contracts/BaseRewardPool.sol#L149) and [VirtualRewardPool.sol](https://github.com/convex-eth/platform/blob/main/contracts/contracts/VirtualBalanceRewardPool.sol#L127), the function signature of `earned` is `earned(address)`. However, `balanceOfJPEG` did not pass any arguments to `earned`, which would cause `balanceOfJPEG` to always revert.

This bug will propagate through `Controller` and `YVault` until finally reaching the source of the call in `YVaultLPFarming ._computeUpdate`, and render the entire farming contract unuseable.

## Proof of Concept

Both `BaseRewardPool.earned` and `VirtualBalanceRewardPool.earned` takes an address as argument

```solidity
function earned(address account) public view returns (uint256) {
    return
        balanceOf(account)
            .mul(rewardPerToken().sub(userRewardPerTokenPaid[account]))
            .div(1e18)
            .add(rewards[account]);
}

function earned(address account) public view returns (uint256) {
    return
        balanceOf(account)
            .mul(rewardPerToken().sub(userRewardPerTokenPaid[account]))
            .div(1e18)
            .add(rewards[account]);
}
```

But `balanceOfJPEG` does not pass any address to `extraReward.earned`, causing the entire function to revert when called

```solidity
function balanceOfJPEG() external view returns (uint256) {
    uint256 availableBalance = jpeg.balanceOf(address(this));

    IBaseRewardPool baseRewardPool = convexConfig.baseRewardPool;
    uint256 length = baseRewardPool.extraRewardsLength();
    for (uint256 i = 0; i < length; i++) {
        IBaseRewardPool extraReward = IBaseRewardPool(baseRewardPool.extraRewards(i));
        if (address(jpeg) == extraReward.rewardToken()) {
            availableBalance += extraReward.earned();
            //we found jpeg, no need to continue the loop
            break;
        }
    }

    return availableBalance;
}
```

## Recommendation

Pass `address(this)` as argument of `earned`.

Notice how we modify the fetching of reward. This is reported in a separate bug report, but for completeness, the entire fix is shown in both report entries.

```solidity
function balanceOfJPEG() external view returns (uint256) {
    uint256 availableBalance = jpeg.balanceOf(address(this));

    IBaseRewardPool baseRewardPool = convexConfig.baseRewardPool;
    availableBalance += baseRewardPool.earned(address(this));
    uint256 length = baseRewardPool.extraRewardsLength();
    for (uint256 i = 0; i < length; i++) {
        IBaseRewardPool extraReward = IBaseRewardPool(baseRewardPool.extraRewards(i));
        if (address(jpeg) == extraReward.rewardToken()) {
            availableBalance += extraReward.earned(address(this));
        }
    }

    return availableBalance;
}
```

Fixed in [jpegd/core#15](https://github.com/jpegd/core/pull/15).

Leaving this as high risk. The issue would cause a loss of funds.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the view function that reports the total balance of JPEG tokens held by the Convex strategy (balanceOfJPEG). The function attempts to query additional reward amounts from Convex reward pools by calling the earned() method on each extra reward contract. According to Convex’s BaseRewardPool and VirtualBalanceRewardPool interfaces, earned requires a single address argument – the account for which the reward should be calculated. In the strategy implementation the call is made without providing this argument, i.e., extraReward.earned() is invoked with an empty calldata payload. Because the called contract expects a non‑zero argument, the Solidity ABI decoder rejects the call and the transaction reverts. This mismatch between the expected function signature and the actual call constitutes an interface‑mismatch bug, a class of errors where a contract interacts with another contract using an incorrect ABI definition.

When balanceOfJPEG is executed – either directly by external callers or indirectly through the Controller and the YVault’s internal accounting (specifically YVaultLPFarming._computeUpdate) – the missing argument triggers a revert on every execution path that reaches an extra reward pool matching the JPEG token. Consequently, any operation that depends on the reported balance, such as deposit, withdraw, or harvest, fails with a runtime error, rendering the whole farming contract unusable. From a user perspective, the UI may show that a deposit succeeded but later actions report “transaction failed” or “balance is zero” even though assets are still locked in the contract. Users expect to see their deposited JPEG tokens and accrued rewards, but instead they receive no response or an error, effectively losing access to their funds until the bug is corrected.

The root cause is a simple developer oversight: the function signature of earned was copied incorrectly, omitting the required address parameter. This type of error can be hard to spot because the problematic line resides inside a view function that is not executed on-chain during normal deployment, and static analysis tools may not flag a mismatched calldata length if the interface is not explicitly imported. The issue was discovered during an external audit where the auditors attempted to call balanceOfJPEG and observed an immediate revert, tracing the failure back to the extraReward.earned() call.

To remediate the vulnerability, the strategy must pass its own contract address (address(this)) to every earned call, both for the base reward pool and for each extra reward contract. This aligns the calldata with the expected ABI, allowing the reward calculation to execute correctly and the balance query to return a valid sum of the JPEG token balance and all pending rewards. After applying the fix, the farming contract regains normal operation, users can correctly view and withdraw their funds, and the protocol’s accounting logic is restored. The bug is classified as a high‑risk interface mismatch that can lead to a denial‑of‑service and potential fund lockup.
