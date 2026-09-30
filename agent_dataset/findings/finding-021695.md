---
id: 21695
severity: "High"
---

# `AuraVault::claim` reward calculation does not deduct fees from reward amount, causing DoS or extra rewards lost

## Description

`AuraVault::claim` allows users to claim rewards corresponding to the amount of `WETH` they are depositing in the same call.

Prior to sending rewards to `msg.sender`, a percentage of the rewards is sent to the `vault locker rewards`. However, the percentage of the rewards sent to the `vault locker rewards` is not deducted from the amount that is sent to the caller. The entire `reward amount` is sent to `msg.sender`.

This is problematic, as it creates two possible scenarios:
1. Contract attempts to send more reward tokens than it holds, causing DoS.
2. Contract successfully sends extra reward tokens, essentially stealing rewards from others.

Therefore, the impact ranges from `stolen funds` to `Denial of Service`.

## Proof of Concept

As users interact with the `AuraVault` contract, the contract will accumulate rewards through interaction with an external [rewards contract](https://etherscan.io/address/0x2a14db8d09db0542f6a371c0cb308a768227d67d#code), which acts as an ERC-4626 vault.

Users can deposit, withdraw, redeem, and _claim_ rewards:

[AuraVault.sol#L275-L310](https://github.com/code-423n4/2024-07-loopfi/blob/main/src/vendor/AuraVault.sol#L275-L310)

```solidity
/**
 * @notice Allows anyone to claim accumulated rewards by depositing WETH instead
 * @param amounts An array of reward amounts to be claimed ordered as [rewardToken, secondaryRewardToken]
 * @param maxAmountIn The max amount of WETH to be sent to the Vault
 */
function claim(uint256[] memory amounts, uint256 maxAmountIn) external returns (uint256 amountIn) {
    // Claim rewards from Aura reward pool
    IPool(rewardPool).getReward();

    // Compute assets amount to be sent to the Vault
    VaultConfig memory _config = vaultConfig;
    amountIn = _previewReward(amounts[0], amounts[1], _config);

    // Transfer assets to Vault
    require(amountIn <= maxAmountIn, "!Slippage");
    IERC20(asset()).safeTransferFrom(msg.sender, address(this), amountIn);

    // Compound assets into "asset" balance
    IERC20(asset()).safeApprove(rewardPool, amountIn);
    IPool(rewardPool).deposit(amountIn, address(this));

    // Distribute BAL rewards
    IERC20(BAL).safeTransfer(_config.lockerRewards, (amounts[0] * _config.lockerIncentive) / INCENTIVE_BASIS);
    IERC20(BAL).safeTransfer(msg.sender, amounts[0]);

    // Distribute AURA rewards
    if (block.timestamp <= INFLATION_PROTECTION_TIME) {
        IERC20(AURA).safeTransfer(_config.lockerRewards, (amounts[1] * _config.lockerIncentive) / INCENTIVE_BASIS);
        IERC20(AURA).safeTransfer(msg.sender, amounts[1]);
    } else {
        // after INFLATION_PROTECTION_TIME
        IERC20(AURA).safeTransfer(_config.lockerRewards, IERC20(AURA).balanceOf(address(this)));
    }

    emit Claimed(msg.sender, amounts[0], amounts[1], amountIn);
}
```

Firstly, rewards are claimed from the `Aura reward pool`, proceeded by a call to `_previewReward()` to calculate the amount of `WETH` the caller must deposit to receive the amount of rewards they have specified.

The issue is with the transferring of rewards. We can see the `vault locker rewards` receives a percentage of the rewards, calculated by `(amounts[0] * _config.lockerIncentive) / INCENTIVE_BASIS)`.

However, the entire amount of rewards is still sent to the caller, without accounting for the percentage that was just sent to the `vault locker rewards`. Therefore, this call is sending extra rewards to the caller.

As mentioned, this leads to two scenarios:
1. DoS due to insufficient rewards.
2. Extra rewards successfully sent to the caller, essentially stealing rewards from others.

Consider the following scenario:
1. Alice decides to deposit `WETH` and claim `BAL` and `AURA` rewards via a call to `AuraVault::claim`. `_config.lockerIncentive` is set to 1000 and `INCENTIVE_BASIS` is set to 10000, effectively setting the fee portion to 10%.
2. Alice sets `amounts[0] = 100e18 BAL` and `amount[1] = 100e18 AURA`.
3. `IPool(rewardPool).getReward();` is called, setting the rewards held in the `AuraVault` contract to `100e18 BAL` and `100e18 AURA`.
4. `IERC20(BAL).safeTransfer(_config.lockerRewards, (amounts[0] * _config.lockerIncentive) / INCENTIVE_BASIS);` call sends `100e18 * 1000 / 10000 = 10e18` `BAL` tokens to `_config.lockerRewards`, which is the `vault locker rewards`.
5. The `AuraVault` contract now holds `90e18 BAL` and `100e18 AURA`.
6. `IERC20(BAL).safeTransfer(msg.sender, amounts[0]);` attempts to send `100e18 BAL` to `msg.sender`; however, `10e18` was already sent to `locker rewards`, so this call will DoS due to insufficient funds.

The call will revert in the case described above, and Alice would have to specify a lower amount of rewards (i.e., 50e18 BAL and AURA), but we can see that the contract will still send more rewards than intended, effectively stealing rewards from others.

## Recommendation

Ensure the amount sent to the locker is deducted from the amount sent to the caller:

```solidity
/**
 * @notice Allows anyone to claim accumulated rewards by depositing WETH instead
 * @param amounts An array of reward amounts to be claimed ordered as [rewardToken, secondaryRewardToken]
 * @param maxAmountIn The max amount of WETH to be sent to the Vault
 */
function claim(uint256[] memory amounts, uint256 maxAmountIn) external returns (uint256 amountIn) {
    // Claim rewards from Aura reward pool
    IPool(rewardPool).getReward();

    // Compute assets amount to be sent to the Vault
    VaultConfig memory _config = vaultConfig;
    amountIn = _previewReward(amounts[0], amounts[1], _config);

    // Transfer assets to Vault
    require(amountIn <= maxAmountIn, "!Slippage");
    IERC20(asset()).safeTransferFrom(msg.sender, address(this), amountIn);

    // Compound assets into "asset" balance
    IERC20(asset()).safeApprove(rewardPool, amountIn);
    IPool(rewardPool).deposit(amountIn, address(this));

    // Distribute BAL rewards
    uint256 fee = (amounts[0] * _config.lockerIncentive) / INCENTIVE_BASIS;
    uint256 amount = amounts[0] - fee;
    IERC20(BAL).safeTransfer(_config.lockerRewards, fee);
    IERC20(BAL).safeTransfer(msg.sender, amount);

    // Distribute AURA rewards
    if (block.timestamp <= INFLATION_PROTECTION_TIME) {
        fee = (amounts[1] * _config.lockerIncentive) / INCENTIVE_BASIS;
        amount = amounts[1] - fee;
        IERC20(BAL).safeTransfer(_config.lockerRewards, fee);
        IERC20(BAL).safeTransfer(msg.sender, amount);
    } else {
        // after INFLATION_PROTECTION_TIME
        IERC20(AURA).safeTransfer(_config.lockerRewards, IERC20(AURA).balanceOf(address(this)));
    }

    emit Claimed(msg.sender, amounts[0], amounts[1], amountIn);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

An over‑payment bug exists in the AuraVault claim function where the contract transfers a fee to the locker rewards but does not subtract that fee from the amount that is subsequently sent to the caller. The function first calculates a locker incentive as a percentage of each reward token, sends that percentage to the configured locker address, and then sends the full declared reward amount to msg.sender. Because the fee amount is not deducted, two distinct failure modes can occur. If the contract’s balance of the reward token is lower than the declared amount after the fee transfer, the second transfer attempts to move more tokens than are available, causing the transaction to revert and effectively denying service to the caller and any subsequent users. If the contract holds enough tokens, the caller receives the full declared amount in addition to the fee that was already sent to the locker, resulting in an unintended surplus of tokens that are taken from the pool of other participants. The bug is triggered whenever a user calls claim with non‑zero lockerIncentive, which is the case for both BAL and AURA rewards before the inflation‑protection deadline. The affected parties include any user attempting to claim rewards, the protocol’s reward accounting, and token holders whose share of the reward pool is reduced. The issue was discovered during a manual audit that examined the reward distribution logic and noticed that the net amount sent to the user was not recomputed after the fee transfer. It can be hard to notice because both transfers succeed and there is no explicit balance check after the fee deduction. From a user’s perspective the expectation is to receive exactly the amount specified in the claim call, but the contract may either revert leaving the user with no tokens or deliver more tokens than expected, breaking the business rule that total distributed rewards must not exceed the pool balance. The vulnerability belongs to the class of fee‑miscalculation or double‑spend bugs where a fee is paid but not accounted for in the subsequent payout. The recommended fix is to compute the net reward as amount minus fee and transfer only that net amount to the caller, or to deduct the fee from the stored reward balance before any transfer, thereby preserving the accounting invariant.
