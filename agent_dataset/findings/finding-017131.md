---
id: 17131
severity: "High"
---

# function `withdrawETH` from `GiantMevAndFeesPool` can steal most of eth because of idleETH is reduced before burning token

## Description

The contract GiantMevAndFeesPool override the function totalRewardsReceived:
```solidity
return address(this).balance + totalClaimed - idleETH;
```
The function totalRewardsReceived is used as the current rewards balance to caculate the unprocessed rewards in the function `SyndicateRewardsProcessor._updateAccumulatedETHPerLP`
```solidity
uint256 received = totalRewardsReceived();
uint256 unprocessed = received - totalETHSeen;
```
But it will decrease the `idleETH` first and then burn the lpTokenETH in the function `GiantMevAndFeesPool.withdrawETH`. The lpTokenETH burn option will trigger `GiantMevAndFeesPool.beforeTokenTransfer` which will call _updateAccumulatedETHPerLP and send the accumulated rewards to the msg sender. Because of the diminution of the idleETH, the `accumulatedETHPerLPShare` is added out of thin air. So the attacker can steal more eth from the GiantMevAndFeesPool.

## Proof of Concept

I wrote a test file for proof, but there is another bug/vulnerability which will make the `GiantMevAndFeesPool.withdrawETH` function break down. I submitted it as the other finding named “GiantLP with a transferHookProcessor cant be burned, users’ funds will be stuck in the Giant Pool”. You should fix it first by modifying the code <https://github.com/code-423n4/2022-11-stakehouse/blob/main/contracts/liquid-staking/GiantMevAndFeesPool.sol#L161-L166> to :
```solidity
if (_to != address(0)) {
    _distributeETHRewardsToUserForToken(
        _to,
        address(lpTokenETH),
        lpTokenETH.balanceOf(_to),
        _to
    );
}
```
I know modifying the project source code is controversial. Please believe me it’s a bug needed to be fixed and it’s independent of the current vulnerability.

test:  
test/foundry/TakeFromGiantPools2.t.sol
```solidity
pragma solidity ^0.8.13;

// SPDX-License-Identifier: MIT

import "forge-std/console.sol";
import {GiantPoolTests} from "./GiantPools.t.sol";

contract TakeFromGiantPools2 is GiantPoolTests {
    function testDWUpdateRate2() public{
        address feesAndMevUserOne = accountOne; vm.deal(feesAndMevUserOne, 4 ether);
        address feesAndMevUserTwo = accountTwo; vm.deal(feesAndMevUserTwo, 4 ether);
        // Deposit ETH into giant fees and mev
        vm.startPrank(feesAndMevUserOne);
        giantFeesAndMevPool.depositETH{value: 4 ether}(4 ether);
        vm.stopPrank();
        vm.startPrank(feesAndMevUserTwo);
        giantFeesAndMevPool.depositETH{value: 4 ether}(4 ether);
        giantFeesAndMevPool.withdrawETH(4 ether);
        vm.stopPrank();
        console.log("user one:", getBalance(feesAndMevUserOne));
        console.log("user two(attacker):", getBalance(feesAndMevUserTwo));
        console.log("giantFeesAndMevPool:", getBalance(address(giantFeesAndMevPool)));
    }

    function getBalance(address addr) internal returns (uint){
        // just ETH
        return addr.balance;  // + giantFeesAndMevPool.lpTokenETH().balanceOf(addr);
    }

}
```
run test:
```bash
forge test --match-test testDWUpdateRate2 -vvv
```
test log:
```
Logs:
  user one: 0
  user two(attacker): 6000000000000000000
  giantFeesAndMevPool: 2000000000000000000
```
The attacker stole 2 eth from the pool.

## Recommendation

`idleETH -= _amount;` should be after the `lpTokenETH.burn`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the GiantMevAndFeesPool contract where the function withdrawETH reduces the idleETH accounting variable before burning the lpTokenETH. The contract overrides totalRewardsReceived to return the pool balance plus totalClaimed minus idleETH. This value is used by the reward processor to compute the amount of unprocessed rewards as received minus totalETHSeen. When withdrawETH is called, idleETH is decreased first, which lowers the reported totalRewardsReceived. Immediately afterwards the burn of lpTokenETH triggers the beforeTokenTransfer hook, which calls _updateAccumulatedETHPerLP. Because idleETH has already been reduced, the calculation of unprocessed rewards becomes artificially larger, causing the accumulatedETHPerLPShare to increase without any real ETH being added to the pool. The attacker’s withdraw call therefore receives more ETH than they are entitled to, effectively creating ETH out of thin air. The exploit works whenever a user invokes withdrawETH while idleETH is non‑zero; the token burn hook distributes the inflated rewards to the caller. Honest users see their balances reduced or even become zero, while the attacker’s balance grows. The issue was discovered during a security audit when a test showed that after two users deposited 4 ether each, the attacker could withdraw 6 ether while the pool retained only 2 ether. The bug is subtle because idleETH is intended to track unallocated ETH, and its premature reduction is not obvious in the reward‑distribution logic, making the extra reward appear as a normal accounting update. To remediate, the contract should update idleETH after the lpTokenETH burn, or otherwise ensure that totalRewardsReceived reflects the true pool balance before any reward distribution hook runs. This restores the invariant that the sum of claimed rewards and idleETH never exceeds the contract’s ETH balance, preventing the creation of phantom ETH and protecting all LP token holders from loss.
