---
id: 25157
severity: "Medium"
---

# Depositing to another receiver othan than msg.sender will lead to stuck funds by increasing avgStart without claiming

## Description



## Proof of Concept

Paste the following test in `StakedEXA.t.sol` to confirm that `address(this)` deposits more without claiming.

```solidity
function test_POC_increaseBalance_withoutClaim() external {
  uint256 assets = 1e18;
  uint256 time = minTime;

  exa.mint(address(this), assets);
  stEXA.deposit(assets, address(this));

  uint256 initTime = block.timestamp * 1e18;
  skip(time + 1);
  uint256 finalTime = block.timestamp * 1e18;

  assertEq(rA.balanceOf(address(this)), 0);
  assertEq(stEXA.avgStart(address(this)), initTime);
  assertEq(stEXA.rawClaimable(rA, address(this), assets), 20833367779982251207);
  assertEq(stEXA.earned(rA, address(this), assets), 41666735559964287164);

  address anotherAccount = makeAddr("AnotherAccount");
  exa.mint(anotherAccount, assets);
  vm.startPrank(anotherAccount);
  exa.approve(address(stEXA), assets);
  stEXA.deposit(assets, address(this));
  vm.stopPrank();

  uint256 newAssets = 2*assets;

  assertEq(rA.balanceOf(address(this)), 0);
  assertEq(stEXA.avgStart(address(this)), (initTime + finalTime) / 2);
  assertEq(stEXA.rawClaimable(rA, address(this), newAssets), 0);
  assertEq(stEXA.earned(rA, address(this), newAssets), 41666735559964287164);
}
```

## Impact

The funds are stuck for much longer than they are supposed to. The duration is `24 weeks` in the tests, so users can have to wait up to 24 weeks more if they do a really big deposit while having fully claimable rewards. Additionally, in case they decide to withdraw after depositing, before the rewards vest again, they will lose these funds to savings.

## Recommendation

Claiming should be made to the receiver of the funds, `to`. The `_claim()` function should be adapted to receiver an `account` argument.
