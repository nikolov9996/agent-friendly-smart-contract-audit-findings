---
id: 19597
severity: "High"
---

# Users staking via the `SurplusGuildMinter` can be immediately slashed when staking into a gauge that had previously incurred a loss

## Description

User’s can stake into a gauge directly via the `GuildToken` or indirectly via the `SurplusGuildMinter`. When a user stakes into a new gauge (i.e. their weight goes from `0` to `> 0`) via `GuildToken::incrementGauge`, their `lastGaugeLossApplied` mapping for this gauge, which is how the system keeps track of whether or not the user deserves to be slashed, is set to the current timestamp:

[GuildToken.sol#L247-L256](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/tokens/GuildToken.sol#L247-L256)

```solidity
        uint256 _lastGaugeLoss = lastGaugeLoss[gauge];
        uint256 _lastGaugeLossApplied = lastGaugeLossApplied[gauge][user];
        if (getUserGaugeWeight[user][gauge] == 0) {
            lastGaugeLossApplied[gauge][user] = block.timestamp;
        } else {
            require(
                _lastGaugeLossApplied >= _lastGaugeLoss,
                "GuildToken: pending loss"
            );
        }
```

This ensures that any loss that occurred in the gauge, before the user staked, will result in the following condition: `lastGaugeLossApplied[gauge][user] > lastGaugeLoss[gauge]`. This means the user staked into the gauge after the gauge experienced a loss and therefore, they can not be slashed:

[GuildToken.sol#L133-L140](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/tokens/GuildToken.sol#L133-L140)

```solidity
    function applyGaugeLoss(address gauge, address who) external {
        // check preconditions
        uint256 _lastGaugeLoss = lastGaugeLoss[gauge];
        uint256 _lastGaugeLossApplied = lastGaugeLossApplied[gauge][who];
        require(
            _lastGaugeLoss != 0 && _lastGaugeLossApplied < _lastGaugeLoss,
            "GuildToken: no loss to apply"
        );
```

The above function showcases the requirements that need to be met in order for a user to be slashed: the user must have been staked in the gauge when the gauge experienced a loss in order for the user to be slashed. With this in mind, let us observe the process that occurs when users stake via the `SurplusGuildMinter`:

When a user stakes into a gauge via the `SurplusGuildMinter::stake` function the `SurplusGuildMinter::getRewards` function is invoked:

[SurplusGuildMinter.sol#L216-L236](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L216-L236)

```solidity
    function getRewards(
        address user,
        address term
    )
        public
        returns (
            uint256 lastGaugeLoss, // GuildToken.lastGaugeLoss(term)
            UserStake memory userStake, // stake state after execution of getRewards()
            bool slashed // true if the user has been slashed
        )
    {
        bool updateState;
        lastGaugeLoss = GuildToken(guild).lastGaugeLoss(term);
        if (lastGaugeLoss > uint256(userStake.lastGaugeLoss)) {
            slashed = true;
        }

        // if the user is not staking, do nothing
        userStake = _stakes[user][term];
        if (userStake.stakeTime == 0)
            return (lastGaugeLoss, userStake, slashed);
```

As seen above, this function will retrieve the `lastGaugeLoss` for the specified gauge (`term`) the user is staking into and will identify this user as being slashed, i.e. `slashed = true`, if `lastGaugeLoss > userStake.lastGaugeLoss`. The issue lies in the fact that, at this point in the code execution, the `userStake` struct is a freshly initialized memory struct and therefore, all of the struct’s fields are set to `0`. Thus, the check on lines 229-230 are really doing the following:

```solidity
            if (lastGaugeLoss > uint256(0)) {
                slashed = true;
            }
```

The above code will always set `slashed` to `true` if the specified gauge has experienced any loss in its history. Therefore, a gauge can have experienced a loss, been off-boarded, and then been re-onboarded at a future time and the `SurplusGuildMinter` will consider any user who stakes into this gauge to be `slashed`.

The code execution will then continue to lines 235-236, where the user’s stake is retrieved from storage (it is initialized to all `0`’s since the user has not staked yet) and if the `stakeTime` field is `0` (it is), the execution returns to the `GuildToken::stake` function:

[SurplusGuildMinter.sol#L114-L125](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L114-L125)

```solidity
    function stake(address term, uint256 amount) external whenNotPaused {
        // apply pending rewards
        (uint256 lastGaugeLoss, UserStake memory userStake, ) = getRewards(
            msg.sender,
            term
        );

        require(
            lastGaugeLoss != block.timestamp,
            "SurplusGuildMinter: loss in block"
        );
        require(amount >= MIN_STAKE, "SurplusGuildMinter: min stake");
```

The above code illustrates the only validation checks that are performed in this `stake` function. As long as the user is not attempting to stake into a gauge in the same block that the gauge experienced a loss, and the user is staking at least `1e18`, the user’s `stake` position will be initialized (the user will be allowed to stake their `Credit`):

[SurplusGuildMinter.sol#L139-L150](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L139-L150)

```solidity
        userStake = UserStake({
            stakeTime: SafeCastLib.safeCastTo48(block.timestamp),
            lastGaugeLoss: SafeCastLib.safeCastTo48(lastGaugeLoss),
            profitIndex: SafeCastLib.safeCastTo160(
                ProfitManager(profitManager).userGaugeProfitIndex(
                    address(this),
                    term
                )
            ),
            credit: userStake.credit + SafeCastLib.safeCastTo128(amount),
            guild: userStake.guild + SafeCastLib.safeCastTo128(guildAmount)
        });
        _stakes[msg.sender][term] = userStake;
```

The user would naturally perform the next actions: They can call `SurplusGuildMinter::getRewards` when they want to receive rewards and they can call `SurplusGuildMinter::unstake` when they want to unstake from their position, i.e. withdraw their deposited `Credit`. It is important to note that when the `unstake` function is called, similar to the `stake` function, the `getRewards` function will first be invoked. As we previously observed, the `getRewards` function will consider the user `slashed` if the gauge had previously experienced any loss in its history. Therefore, after a user has staked, any call to `getRewards` will result in the following logic to execute:

[SurplusGuildMinter.sol#L274-L289](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L274-L289)

```solidity
        if (slashed) {
            emit Unstake(block.timestamp, term, uint256(userStake.credit));
            userStake = UserStake({
                stakeTime: uint48(0),
                lastGaugeLoss: uint48(0),
                profitIndex: uint160(0),
                credit: uint128(0),
                guild: uint128(0)
            });
            updateState = true;
        }

        // store the updated stake, if needed
        if (updateState) {
            _stakes[user][term] = userStake;
        }
```

As we can see above, when a user calls `getRewards` or `unstake` after staking into a gauge that has experienced a loss sometime in its history, the user’s `stake` position will be deleted (slashed). If the user is attempting to unstake then the execution flow will continue in the `unstake` function:

[SurplusGuildMinter.sol#L158-L166](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L158-L166)

```solidity
    function unstake(address term, uint256 amount) external {
        // apply pending rewards
        (, UserStake memory userStake, bool slashed) = getRewards(
            msg.sender,
            term
        );

        // if the user has been slashed, there is nothing to do
        if (slashed) return;
```

Since the user has been considered `slashed`, the execution will return on line 166 and the user will not be allowed to withdraw their staked `Credit`.

I would also like to note that the user will still have a chance to receive some `earned Credit` after the gauge experiences a profit. However, since the user is considered `slashed`, they will not be given any `guild rewards`:

[SurplusGuildMinter.sol#L247-L264](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L247-L264)

```solidity
        uint256 deltaIndex = _profitIndex - _userProfitIndex;

        if (deltaIndex != 0) {
            uint256 creditReward = (uint256(userStake.guild) * deltaIndex) /
                1e18;
            uint256 guildReward = (creditReward * rewardRatio) / 1e18;
            if (slashed) {
                guildReward = 0;
            }

            // forward rewards to user
            if (guildReward != 0) {
                RateLimitedMinter(rlgm).mint(user, guildReward);
                emit GuildReward(block.timestamp, user, guildReward);
            }
            if (creditReward != 0) {
                CreditToken(credit).transfer(user, creditReward);
            }
```

As seen above, if the user is eligible to claim rewards (the gauge they staked into has experienced a profit), then they will be sent `creditReward` of `Credit`. However, since they are considered `slashed`, their `guildReward` is set to `0`. This scenario will only occur if no one calls `getReward` for this user before the gauge generates a profit. If any call to `getReward` for this user is invoked before that, the user will not be able to receive any rewards and in both situations they will lose their staked `Credit`.

An additional, lesser effect, is that the `Guild` which was minted on behalf of the user who staked will not be unstaked from the gauge, it will not be burned, and the `RateLimitedGuildMinter`’s buffer will not be replenished. I.e. the following code from the `unstake` function will not execute:

[SurplusGuildMinter.sol#L205-L208](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/main/src/loan/SurplusGuildMinter.sol#L205-L208)

```solidity
        // burn GUILD
        GuildToken(guild).decrementGauge(term, guildAmount);
        RateLimitedMinter(rlgm).replenishBuffer(guildAmount);
        GuildToken(guild).burn(guildAmount);
```

## Proof of Concept

The following test describes the main impact highlighted above, in which a user stakes into a previously lossy gauge and is immediately slashed:

Place the following test inside of `test/unit/loan/SurplusGuildMinter.t.sol`:

```solidity
        function testUserImmediatelySlashed() public {
            // initial state
            assertEq(guild.getGaugeWeight(term), 50e18);

            // add credit to surplus buffer
            credit.mint(address(this), 100e18);
            credit.approve(address(profitManager), 50e18);
            profitManager.donateToSurplusBuffer(50e18);

            // term incurs loss
            profitManager.notifyPnL(term, -50e18);
            assertEq(guild.lastGaugeLoss(term), block.timestamp);

            // term offboarded
            guild.removeGauge(term);
            assertEq(guild.isGauge(term), false);

            // time passes and term is re-onboarded
            vm.roll(block.number + 100);
            vm.warp(block.timestamp + (100 * 13));
            guild.addGauge(1, term);
            assertEq(guild.isGauge(term), true);

            // user stakes into term directly
            address user = address(0x01010101);
            guild.mint(user, 10e18);
            vm.startPrank(user);
            guild.incrementGauge(term, 10e18);
            vm.stopPrank();

            // user can un-stake from term
            vm.startPrank(user);
            guild.decrementGauge(term, 10e18);
            vm.stopPrank();

            // user stakes into term via sgm
            credit.mint(user, 10e18);
            vm.startPrank(user);
            credit.approve(address(sgm), 10e18);
            sgm.stake(term, 10e18);
            vm.stopPrank();
            
            // check after-stake state
            assertEq(credit.balanceOf(user), 0);
            assertEq(profitManager.termSurplusBuffer(term), 10e18);
            assertEq(guild.getGaugeWeight(term), 70e18);
            SurplusGuildMinter.UserStake memory userStake = sgm.getUserStake(user, term);
            assertEq(uint256(userStake.stakeTime), block.timestamp);
            assertEq(userStake.lastGaugeLoss, guild.lastGaugeLoss(term));
            assertEq(userStake.profitIndex, 0);
            assertEq(userStake.credit, 10e18);
            assertEq(userStake.guild, 20e18);

            // malicious actor is aware of bug and slashes the user's stake immediately, despite no loss occurring in the gauge
            sgm.getRewards(user, term);

            // check after-getReward state (user was slashed even though no loss has occurred since term was re-onboarded)
            assertEq(credit.balanceOf(user), 0);
            assertEq(profitManager.termSurplusBuffer(term), 10e18);
            assertEq(guild.getGaugeWeight(term), 70e18);
            userStake = sgm.getUserStake(user, term);
            assertEq(uint256(userStake.stakeTime), 0);
            assertEq(userStake.lastGaugeLoss, 0);
            assertEq(userStake.profitIndex, 0);
            assertEq(userStake.credit, 0);
            assertEq(userStake.guild, 0);

            // user tries to unstake but will not receive anything
            uint256 userBalanceBefore = credit.balanceOf(user);
            vm.startPrank(user);
            sgm.unstake(term, 10e18);
            vm.stopPrank();
            uint256 userAfterBalance = credit.balanceOf(user);

            assertEq(userBalanceBefore, 0);
            assertEq(userAfterBalance, 0);
        }
```

## Recommendation

Similar to how the `GuildToken::incrementGauge` function initializes a user’s `lastGaugeLossApplied` value, the `SurplusGuildMinter` should initialize a user’s `userStake.lastGaugeLoss` to `block.timestamp`. It should then compare the `lastGaugeLoss` to the user’s stored `userStake.lastGaugeLoss` instead of comparing the `lastGaugeLoss` to a freshly initialized `userStake` memory struct, whose fields are all `0`.

_Note: For full discussion, see [here](https://github.com/code-423n4/2023-12-ethereumcreditguild-findings/issues/473)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the SurplusGuildMinter contract, which allows users to stake Credit tokens into a gauge that tracks profit and loss. When a user stakes through the minter, the contract calls getRewards to determine whether the user should be considered slashed based on the gauge's last recorded loss. The function retrieves the gauge's lastGaugeLoss value and compares it to the lastGaugeLoss field stored in a freshly created memory struct called userStake. Because this struct is newly allocated, all of its fields, including lastGaugeLoss, are initialised to zero. Consequently, if the gauge has ever experienced a loss in its history, the condition lastGaugeLoss > 0 evaluates to true and the slashed flag is set, even though the user has never been exposed to that loss. The contract then proceeds to delete the user's stake, zeroing out the stored credit and guild balances and preventing any future withdrawal. This behaviour is triggered whenever a gauge that previously incurred a loss is re‑onboarded or when a user stakes into any gauge with a non‑zero loss history via SurplusGuildMinter. The impact is that users lose their deposited Credit, receive no guild rewards, and cannot unstake their position, while the protocol’s internal guild buffer is not replenished. From the user’s perspective the UI shows a successful stake transaction followed by an empty balance and missing rewards, contradicting the expectation that the stake should be retained and withdrawable. The issue was discovered during a security audit that exercised staking, loss, off‑boarding, and re‑on‑boarding scenarios, revealing that the slashing logic incorrectly uses an uninitialised struct rather than the persisted user stake data. The bug is hard to notice because the contract does not revert; it silently clears the stake, making the loss appear as a normal state change rather than an error. The root cause is an initialization and logic error in the loss‑detection routine, a classic case of incorrect state handling that leads to false‑positive slashing. The recommended fix is to initialise the userStake.lastGaugeLoss field to the current block timestamp (or the stored value for the user) when a new stake is created, and to compare the gauge's lastGaugeLoss against this stored value instead of against zero. This aligns the behaviour with the GuildToken.incrementGauge logic, ensuring that only users who were present during an actual loss are subject to slashing, and restores the intended accounting guarantees of the protocol.
