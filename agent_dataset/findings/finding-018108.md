---
id: 18108
severity: "High"
---

# User can lose up to whole stake on vault withdrawal when there are funds locked in the strategy

## Description

ReaperVaultV2’s `withdrawMaxLoss` isn’t honoured when there are any locked funds in the strategy. Locked funds mean that there is a gap between requested and returned amount other than the loss reported. This is valid behavior of a strategy, but in this case realized loss is miscalculated in _withdraw() and a withdrawing user will receive less funds, while having all the shares burned.

## Proof of Concept

`_withdraw()` resets `value` to be `token.balanceOf(address(this))` when the balance isn’t enough for withdrawal:

```solidity
    // Internal helper function to burn {_shares} of vault shares belonging to {_owner}
    // and return corresponding assets to {_receiver}. Returns the number of assets that were returned.
    function _withdraw(
        uint256 _shares,
        address _receiver,
        address _owner
    ) internal nonReentrant returns (uint256 value) {
        ...

        vaultBalance = token.balanceOf(address(this));
        if (value > vaultBalance) {
            value = vaultBalance;
        }

        require(
            totalLoss <= ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR,
            "Withdraw loss exceeds slippage"
        );
    }

    token.safeTransfer(_receiver, value);
    emit Withdraw(msg.sender, _receiver, _owner, value, _shares);
```

Each strategy can return less than `requested - loss` as some funds can be temporary frozen:

```solidity
    /**
     * @dev Withdraws funds and sends them back to the vault. Can only
     *      be called by the vault. _amount must be valid and security fee
     *      is deducted up-front.
     */
    function withdraw(uint256 _amount) external override returns (uint256 loss) {
        require(msg.sender == vault, "Only vault can withdraw");
        require(_amount != 0, "Amount cannot be zero");
        require(_amount <= balanceOf(), "Ammount must be less than balance");

        uint256 amountFreed = 0;
        (amountFreed, loss) = _liquidatePosition(_amount);
        IERC20Upgradeable(want).safeTransfer(vault, amountFreed);
    }
```

The invariant there is `liquidatedAmount + loss <= _amountNeeded`, so `liquidatedAmount + loss < _amountNeeded` is a valid state (due to the funds locked):

```solidity
    /**
     * Liquidate up to `_amountNeeded` of `want` of this strategy's positions,
     * irregardless of slippage. Any excess will be re-invested with `_adjustPosition()`.
     * This function should return the amount of `want` tokens made available by the
     * liquidation. If there is a difference between them, `loss` indicates whether the
     * difference is due to a realized loss, or if there is some other sitution at play
     * (e.g. locked funds) where the amount made available is less than what is needed.
     *
     * NOTE: The invariant `liquidatedAmount + loss <= _amountNeeded` should always be maintained
     */
    function _liquidatePosition(uint256 _amountNeeded)
        internal
        virtual
        returns (uint256 liquidatedAmount, uint256 loss);
```

`_liquidatePosition()` is called in strategy withdraw():

```solidity
    /**
     * @dev Withdraws funds and sends them back to the vault. Can only
     *      be called by the vault. _amount must be valid and security fee
     *      is deducted up-front.
     */
    function withdraw(uint256 _amount) external override returns (uint256 loss) {
        require(msg.sender == vault, "Only vault can withdraw");
        require(_amount != 0, "Amount cannot be zero");
        require(_amount <= balanceOf(), "Ammount must be less than balance");

        uint256 amountFreed = 0;
        (amountFreed, loss) = _liquidatePosition(_amount);
        IERC20Upgradeable(want).safeTransfer(vault, amountFreed);
    }
```

This way there can be `lockedAmount = _amountNeeded - (liquidatedAmount + loss) >= 0`, which is neither a loss, nor withdraw-able at the moment.

As ReaperVaultV2’s `_withdraw()` updates `value` per `if (value > vaultBalance) {value = vaultBalance;}`, the following `totalLoss <= ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR` check do not control for the real loss and allows user to lose up to the whole amount due as `_withdraw()` first burns the full amount of the `_shares` requested and this total loss check for the _rebased_ `value` is the only guard in place:

```solidity
    function _withdraw(
        uint256 _shares,
        address _receiver,
        address _owner
    ) internal nonReentrant returns (uint256 value) {
        require(_shares != 0, "Invalid amount");
        value = (_freeFunds() * _shares) / totalSupply();
        _burn(_owner, _shares);

        if (value > token.balanceOf(address(this))) {
            ...

            vaultBalance = token.balanceOf(address(this));
            if (value > vaultBalance) {
                value = vaultBalance;
            }

            require(
                totalLoss <= ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR,
                "Withdraw loss exceeds slippage"
            );
        }

        token.safeTransfer(_receiver, value);
        emit Withdraw(msg.sender, _receiver, _owner, value, _shares);
    }
```

Suppose there is only one strategy and `90` of the `100` tokens requested is locked at the moment, and there is no loss, just a temporal liquidity squeeze. Say there is no tokens on the vault balance before strategy withdrawal.

ReaperBaseStrategyv4’s `withdraw()` will transfer `10`, report `0` loss, `0 = totalLoss <= ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR = (10 + 0) * withdrawMaxLoss / PERCENT_DIVISOR` check will be satisfied for any viable `withdrawMaxLoss` setting.

Bob the withdrawing user will receive `10` tokens and have `100` tokens worth of the shares burned.

## Recommendation

Consider rewriting the controlling logic so the check be based on initial value:

Now:

```solidity
    vaultBalance = token.balanceOf(address(this));
    if (value > vaultBalance) {
        value = vaultBalance;
    }

    require(
        totalLoss <= ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR,
        "Withdraw loss exceeds slippage"
    );
```

To be, as an example, if treat the loss attributed to the current user only as they have requested the withdrawal:

```solidity
    require(
        totalLoss <= (value * withdrawMaxLoss) / PERCENT_DIVISOR,
        "Withdraw loss exceeds slippage"
    );

    value -= totalLoss;

    vaultBalance = token.balanceOf(address(this));
    require(
        value <= vaultBalance,
        "Not enough funds"
    );
```

Also, `shares` can be updated according to the real value obtained as it is done in yearn:

```solidity
    if value > vault_balance:
        value = vault_balance
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is a mis‑calculation of the withdrawal loss check in ReaperVaultV2 that can cause a user to lose up to the entire amount of their stake when the underlying strategy holds locked funds. The vault’s internal _withdraw function first determines the value of the shares to be redeemed, then immediately burns the corresponding shares. If the strategy cannot release the full amount because some tokens are temporarily locked, the function overwrites the calculated value with the current token balance of the vault (which may be far lower than the original request). The subsequent require statement compares the reported totalLoss against ((value + totalLoss) * withdrawMaxLoss) / PERCENT_DIVISOR, but because totalLoss is zero and value has already been reduced to the available balance, the check always passes. Consequently the contract transfers only the unlocked portion to the user while the full share balance is destroyed, effectively discarding the locked portion. This can happen whenever a strategy’s _liquidatePosition returns less than the requested amount – a legitimate state for many yield strategies – and the vault does not account for that shortfall in its loss guard. From the user’s perspective the UI shows a successful withdrawal, but the received token amount is far smaller than expected, sometimes zero, while their vault share balance disappears. The bug is hard to notice because the contract emits no error; the loss check appears to succeed and the transaction does not revert. The impact is a direct loss of user funds and erosion of trust in the protocol. The vulnerability was discovered during a Code4rena audit by tracing the withdrawal flow and observing that the loss calculation uses the adjusted value rather than the original request. To fix the problem the loss guard should be based on the initial requested value before any balance‑adjustment, and the share burn should occur only after the actual payout is known. Additionally, the vault should either prevent withdrawals when locked funds exist or update the share accounting to reflect the reduced payout, mirroring the approach used by Yearn vaults. This correction restores the intended invariant that users cannot lose more than the configured withdrawMaxLoss percentage and ensures that burned shares correspond to the amount actually transferred.
