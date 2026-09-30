---
id: 23009
severity: "High"
---

# Wrong call order for setTopPoolIdsWithWeights,

## Description

The Masterchef contract allows people to stake an admin-selected token in farms to earn LUM rewards. Each two weeks, MLUM stakers can vote on their favorite pools, and the top pools will earn LUM emissions according to the votes. Admin has to call setTopPoolIdsWithWeights to set those votes and weights to set the reward emission for the next two weeks.
Per the documented call order for setTopPoolIdsWithWeights:
```solidity
/**
* @dev Set farm pools with their weight;
*
* WARNING:
* Caller is responsible to updateAll oldPids on masterChef before using this function
* and also call updateAll for the new pids after.
*
* @param pids - list of pids
* @param weights - list of weights
*/
```
We show that this call order is wrong, and will result in wrong rewards distribution.
There is a global parameter lumPerSecond, set by the admin. Whenever updateAll is called for a set of pools:
• Let the total weight of all votes across all top pools be totalWeight
• Let the current weight of a pool Pid be weightPid. This weight can be set by the admin using setTopPoolIdsWithWeights
• Pool Pid will earn totalLumRewardForPid = (lumPerSecond * weightPid / totalWeight) * (elapsed_time), i.e. each second it earns lumPerSecond times its percentage of voted weight weightPid across the total weight all top pools totalWeight.
/src/MasterchefV2.sol#L522-L525
Now, the function updateAll does the following:
• For each pool, fetch its weight and calculate its totalLumRewardForPid since last update
• Mint that calculated amount of LUM
• updateAccDebtPerShare i.e. distribute rewards since the last updated time
/src/MasterchefV2.sol#L526-L528
pools before calling setTopPoolIdsWithWeights() for the new pools, and then calling updateAll() on the new pools.
We claim that, using this call order, a pool will be wrongly updated if it's within the set newPid but not in oldPid, and the functions are called with this order. Take this example.
Pools that have just made it into the top pools will have already accrued rewards for time intervals it wasn't in the top pools. Rewards are thus severely inflated.

## Proof of Concept

Let LUM per second = 1. We assume all farms were created and registered at time 0:
• At time 1000: there are two pools, A and B making it into the top pools. Weight = 1 both.
– updateAll for oldPid. There are no old Pids
– setTopPoolIdsWithWeights: Pool A and pool B now have weight = 1.
– updateAll for newPid (A and B). 1000 seconds passed, each pool accrued 500 LUM for having 50% weight despite just making it into the top weighted pools
• At time 2000: a new pool C makes it into the pool, while pool B is no longer in the top. Weight = 1 both.
– updateAll for oldPid (A and B).
* For pool A, 1000 seconds passed. It earns 500 LUM
* For pool B, 1000 seconds passed. It earns 500 LUM
– setTopPoolIdsWithWeights: Pool A and pool C now have weight = 1.
– updateAll for newPid (A and C).
* For pool A, 0 seconds passed. It earns 0 LUM
* For pool C, 2000 seconds passed. It earns 1000 LUM
The end result is that, at time 2000:
• Pool A accrued 1000 LUM
• Pool B accrued 1000 LUM
• Pool C accrued 1000 LUM
Where the correct result should be:
• Pool A accrued 500 LUM, it was in the top pools in time 1000 to 2000
• Pool B accrued 500 LUM, it was in the top pools in time 1000 to 2000
• Pool C accrued 0 LUM, it only started being in the top pools from timestamp 2000
In total, 3000 LUM has been distributed from timestamps 1000 to 2000, despite the emission rate should be 1 LUM per second. In fact, LUM has been wrongly distributed since timestamp 1000, as both pool A and B never made it into the top pools but still immediately accrued 500 LUM each.
This is because if a pool is included in an updateAll call after its weight has been set, its last updated timestamp is still in the past. Therefore when updateAll is called, the new weights are applied across the entire interval since it was last updated (i.e. a far point in the past).
Coded PoC
We provide a coded PoC to prove the impact of timestamp 1000. We add two farms A and B. LUM per second is set to 1000 wei per second. We also have a single staker Alice depositing into farm A.
We have two tests to compare the results:
• Both tests set the pool weights at time 1000, then output Alice's pending reward right after that.
• There are no oldPids, so there's no need to call updateAll() on anything before setting weights.
• In one test, we call updateAll(newPids) after calling setTopPoolIdsWithWeights().
• In the other test, we call updateAll(newPids) before calling setTopPoolIdsWithWeights().
We output the pending rewards of Alice for comparison.
First, change the function mint() of contract MockERC20 to be the following:
```solidity
function mint(address _to, uint256 _amount) external returns (uint256) {
    _mint(_to, _amount);
    return _amount;
}
```
Then, create a new test file MasterChefTest.t.sol:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "forge-std/Test.sol";
import "openzeppelin-contracts-upgradeable/access/OwnableUpgradeable.sol";
import {SafeERC20, IERC20} from "openzeppelin/token/ERC20/utils/SafeERC20.sol";
import "../src/transparent/TransparentUpgradeableProxy2Step.sol";
import "openzeppelin/token/ERC721/ERC721.sol";
import "openzeppelin/token/ERC20/ERC20.sol";
import {ERC20Mock} from "./mocks/ERC20.sol";
import {MasterChef} from "../src/MasterChefV2.sol";
import {MlumStaking} from "../src/MlumStaking.sol";
import "../src/Voter.sol";
import "../src/rewarders/BaseRewarder.sol";
import "../src/rewarders/MasterChefRewarder.sol";
import "../src/rewarders/RewarderFactory.sol";
import {IVoter} from "../src/interfaces/IVoter.sol";
import {ILum} from "../src/interfaces/ILum.sol";
import {IRewarderFactory} from "../src/interfaces/IRewarderFactory.sol";
contract MasterChefV2Test is Test {
    address payable immutable DEV = payable(makeAddr("dev"));
    address payable immutable ALICE = payable(makeAddr("alice"));
    address payable immutable BOB = payable(makeAddr("bob"));
    Voter private _voter;
    MlumStaking private _pool;
    MasterChef private _masterChefV2;
    ERC20Mock private farmA;
    ERC20Mock private farmB;
    ERC20Mock private farmC;
    MasterChefRewarder rewarderPoolA;
    MasterChefRewarder rewarderPoolB;
    MasterChefRewarder rewarderPoolC;
    RewarderFactory factory;
    ERC20Mock private _stakingToken;
    ERC20Mock private _rewardToken;
    ERC20Mock private _lumToken;
    uint256[] pIds;
    uint256[] weights;

    function setUp() public {
        vm.prank(DEV);
        _stakingToken = new ERC20Mock("MagicLum", "MLUM", 18);
        vm.prank(DEV);
        _rewardToken = new ERC20Mock("USDT", "USDT", 6);
        vm.prank(DEV);
        address poolImpl = address(new MlumStaking(_stakingToken, _rewardToken));
        _pool = MlumStaking(
            address(
                new TransparentUpgradeableProxy2Step(
                    poolImpl, ProxyAdmin2Step(address(1)),
                    abi.encodeWithSelector(MlumStaking.initialize.selector, DEV)
                )
            )
        );
        address factoryImpl = address(new RewarderFactory());
        factory = RewarderFactory(
            address(
                new TransparentUpgradeableProxy2Step(
                    factoryImpl,
                    ProxyAdmin2Step(address(1)),
                    abi.encodeWithSelector(
                        RewarderFactory.initialize.selector, address(this), new uint8[](0), new address[](0)
                    )
                )
            )
        );
        vm.prank(DEV);
        _lumToken = new ERC20Mock("Lum", "LUM", 18);
        farmA = new ERC20Mock("Farm A", "FARM A", 18);
        farmB = new ERC20Mock("Farm B", "FARM B", 18);
        farmC = new ERC20Mock("Farm C", "FARM C", 18);
        vm.prank(DEV);
        address masterChefImp = address(new MasterChef(ILum(address(_lumToken)), _voter, factory,DEV,1));
        _masterChefV2 = MasterChef(
            address(
                new TransparentUpgradeableProxy2Step(
                    masterChefImp, ProxyAdmin2Step(address(1)),
                    abi.encodeWithSelector(MasterChef.initialize.selector, DEV,DEV)
                )
            )
        );
        vm.prank(DEV);
        _masterChefV2.setLumPerSecond(1000);
        vm.prank(DEV);
        _masterChefV2.setMintLum(true);
        //add 3 farms
        vm.prank(DEV);
        _masterChefV2.add(farmA,IMasterChefRewarder(address(0)));
        vm.prank(DEV);
        _masterChefV2.add(farmB,IMasterChefRewarder(address(0)));
        vm.prank(DEV);
        _masterChefV2.add(farmC,IMasterChefRewarder(address(0)));
        vm.prank(DEV);
        address voterImpl = address(new Voter(_masterChefV2, _pool, factory));
        _voter = Voter(
            address(
                new TransparentUpgradeableProxy2Step(
                    voterImpl, ProxyAdmin2Step(address(1)),
                    abi.encodeWithSelector(Voter.initialize.selector, DEV)
                )
            )
        );
        vm.prank(DEV);
        _voter.updateMinimumLockTime(2 weeks);
        vm.prank(DEV);
        factory.setRewarderImplementation(
            IRewarderFactory.RewarderType.MasterChefRewarder,
            IRewarder(address(new MasterChefRewarder(address(_masterChefV2))))
        );
        vm.prank(DEV);
        _masterChefV2.setVoter(_voter);
    }

    //SetPoolWeightsTest Correct
    function testSetPoolWeightsCorrect() public {
        pIds.push(0);
        pIds.push(1);
        weights.push(500);
        weights.push(500);
        farmA.mint(ALICE, 2 ether);
        vm.prank(ALICE);
        farmA.approve(address(_masterChefV2), 1 ether);
        vm.prank(ALICE);
        _masterChefV2.deposit(0, 1 ether);
        skip(1000);
        vm.prank(DEV);
        _masterChefV2.updateAll(pIds);
        vm.prank(DEV);
        _voter.setTopPoolIdsWithWeights(pIds,weights);
        (uint256[] memory lumRewards,IERC20[] memory tokens,uint256[] memory extraRewards) = _masterChefV2.getPendingRewards(ALICE, pIds);
        console.log("Alice rewards correct:");
        console.log(lumRewards[0]);
    }

    //SetPoolWeightsTest Wrong
    function testSetPoolWeightsWrong() public {
        pIds.push(0);
        pIds.push(1);
        weights.push(500);
        weights.push(500);
        farmA.mint(ALICE, 2 ether);
        vm.prank(ALICE);
        farmA.approve(address(_masterChefV2), 1 ether);
        vm.prank(ALICE);
        _masterChefV2.deposit(0, 1 ether);
        skip(1000);
        vm.prank(DEV);
        _voter.setTopPoolIdsWithWeights(pIds,weights);
        vm.prank(DEV);
        _masterChefV2.updateAll(pIds);
        (uint256[] memory lumRewards,IERC20[] memory tokens,uint256[] memory extraRewards) = _masterChefV2.getPendingRewards(ALICE, pIds);
        console.log("Alice rewards wrong:");
        console.log(lumRewards[0]);
    }
}
```
And the results are:
As shown, in the "correct" test, Alice has not accrued any rewards right after the new weights are set. However, in the "wrong" test, Alice accrues 499999 reward units right after setting.

## Recommendation

All of the pools (oldPids and newPids) should be updated, only then weights should be applied.
In other words, the correct call order should be:
• updateAll should be called for all pools within oldPid or newPid.
• setTopPoolIdsWithWeights should then be called.
Additionally, we think it might be better that setTopPoolIdsWithWeights itself should just call updateAll for all (old and new) pools before updating the pool weights, or at least validate that their last updated timestamp is sufficiently fresh.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect sequence of function calls used to update pool weights and reward accrual in the MasterChef contract. The contract distributes LUM tokens to a set of top‑ranked farms based on a per‑second emission rate (lumPerSecond) multiplied by each pool’s weight divided by the total weight of all top pools. Rewards are minted when the updateAll function is invoked, which calculates the amount earned since the pool’s lastUpdated timestamp. The documented workflow requires the caller to first updateAll for the old pool identifiers, then call setTopPoolIdsWithWeights to assign new weights, and finally updateAll for the newly‑added pools. This order is flawed because when setTopPoolIdsWithWeights is executed before the new pools are updated, the lastUpdated timestamp of those pools remains at the moment they were created, not at the moment the weight change occurs. Consequently, the subsequent updateAll call applies the new weight retroactively over the entire elapsed interval since the pool’s creation, causing rewards to be calculated for a period during which the pool was not actually part of the top‑ranked set. The result is an inflation of minted LUM tokens: pools that have just entered the top list receive rewards for time periods before they were eligible, while pools that have left the top list may retain accrued rewards that should have been halted. From a user’s perspective this manifests as unexpectedly high pending rewards or balances that increase dramatically without any additional staking activity, breaking the expectation that rewards grow proportionally to the time a pool remains in the top set. The impact is high because the protocol’s emission schedule can be exceeded by a factor of two or more, draining the token supply, distorting tokenomics, and potentially devaluing LUM for all participants. The issue appears whenever the admin follows the documented call order, which is the normal operational procedure for rotating top pools every two weeks, making it easy to trigger unintentionally. It was discovered during a security audit through a proof‑of‑concept test that compared the correct and incorrect call sequences, revealing that the wrong order yields 3000 LUM minted over a 1000‑second interval where only 1000 LUM should have been emitted. The bug is hard to notice because the reward numbers still look plausible and the over‑minting is spread across multiple pools, masking the discrepancy in aggregate emission statistics. The proper mitigation is to ensure that all pools—both those being removed and those being added—are updated before any weight changes are applied. This can be achieved by calling updateAll for the union of old and new pool identifiers prior to invoking setTopPoolIdsWithWeights, or by embedding the updateAll logic directly inside setTopPoolIdsWithWeights and validating that each pool’s lastUpdated timestamp is recent. By synchronising timestamps with weight updates, the contract will correctly calculate rewards only for the time intervals during which a pool actually holds a weight, preserving the intended emission rate and preventing accidental over‑distribution of LUM.
