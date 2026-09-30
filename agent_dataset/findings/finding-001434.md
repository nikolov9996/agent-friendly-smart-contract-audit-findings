---
id: 1434
severity: "High"
---

# [WP-H5] `L1Migrator.sol#migrateETH`

## Description

Per the `arb-bridge-eth` code:

all msg.value will deposited to callValueRefundAddress on L2

  * <https://github.com/OffchainLabs/arbitrum/blob/78118ba205854374ed280a27415cb62c37847f72/packages/arb-bridge-eth/contracts/bridge/Inbox.sol#L313>
  * <https://github.com/livepeer/arbitrum-lpt-bridge/blob/ebf68d11879c2798c5ec0735411b08d0bea4f287/contracts/L1/gateway/L1ArbitrumMessenger.sol#L65-L74>

```solidity
uint256 seqNum = inbox.createRetryableTicket{value: _l1CallValue}(
    target,
    _l2CallValue,
    maxSubmissionCost,
    from,
    from,
    maxGas,
    gasPriceBid,
    data
);
```

At L308-L309, ETH held by `BridgeMinter` is withdrawn to L1Migrator:

```solidity
uint256 amount = IBridgeMinter(bridgeMinterAddr)
    .withdrawETHToL1Migrator();
```

However, when calling `sendTxToL2()` the parameter `_l1CallValue` is only the `msg.value`, therefore, the ETH transferred to L2 does not include any funds from `bridgeMinter`.

```solidity
sendTxToL2(
    l2MigratorAddr,
    address(this), // L2 alias of this contract will receive refunds
    msg.value,
    amount,
    _maxSubmissionCost,
    _maxGas,
    _gasPriceBid,
    ""
)
```

As a result, due to lack of funds, `call` with value = amount to `l2MigratorAddr` will always fail on L2.

Since there is no other way to send ETH to L2, all the ETH from `bridgeMinter` is now frozen in the contract.

## Proof of Concept

no poc

## Recommendation

Change to:

```solidity
sendTxToL2(
    l2MigratorAddr,
    address(this), // L2 alias of this contract will receive refunds
    msg.value + amount, // the `amount` withdrawn from BridgeMinter should be added
    amount,
    _maxSubmissionCost,
    _maxGas,
    _gasPriceBid,
    ""
);
```

Fixed in <https://github.com/livepeer/arbitrum-lpt-bridge/pull/51>

Awesome find!

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error in the L1 to L2 ETH migration flow of the Livepeer Arbitrum bridge. When a user calls the `migrateETH` function, the contract withdraws ETH that is held by the `BridgeMinter` contract (via `withdrawETHToL1Migrator`) and stores it in a local variable called `amount`. The withdrawn ETH is intended to be sent to L2 as part of the retryable ticket that funds the call on the destination chain. However, the code that creates the retryable ticket only passes `msg.value` as the `_l1CallValue` argument to `inbox.createRetryableTicket`. The `amount` withdrawn from `BridgeMinter` is passed separately as the L2 call value but is **not** added to the L1 call value that funds the retryable ticket. As a result, the L2 side receives a call with a value (`amount`) that exceeds the funds supplied by the retryable ticket, causing the call to revert on L2 every time. Because there is no alternative mechanism to forward ETH to L2, the withdrawn ETH becomes permanently locked in the `BridgeMinter` contract. The issue manifests as users seeing their ETH disappear after initiating a migration – the transaction appears to succeed on L1, but no funds arrive on L2 and the bridge’s internal balance shows a reduction with no corresponding credit. The problem was uncovered during a Code4rena audit, where the mismatch between the supplied `_l1CallValue` and the required L2 call value was identified. It is difficult to notice because the transaction does not throw an explicit error on L1 and the retryable ticket creation succeeds, hiding the underlying shortfall. The bug belongs to the class of “incorrect value forwarding” or “funds accounting” bugs, where a contract fails to forward all necessary assets to a downstream operation, violating the protocol’s financial assumptions. To remediate, the `_l1CallValue` parameter must be increased to include the withdrawn amount (`msg.value + amount`), ensuring the retryable ticket supplies enough ETH to cover the L2 call. After this correction, the bridge can safely migrate ETH without freezing funds, restoring the expected behavior where the user’s balance on L1 decreases by the migrated amount and the equivalent amount appears on L2.
