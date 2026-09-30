---
id: 22224
severity: "High"
---

# L1 CCIP messages use incorrect `tokensInTransitToL1` value leading to overvalued LST on Metis

## Description

A discrepancy in withdrawal accounting between L1 and L2 chains can lead to an artificial inflation of the share price in the staking system.

In the `L1Transmitter::_executeUpdate` function, note that while actual amount withdrawn from `L1Strategy` is `toWithdraw`, the CCIP message assumes that the full `queuedWithdrawals` is withdrawn. In the scenario where `queuedWithdrawals > canWithdraw`, the CCIP message is sending an inflated value for `tokensInTransitToL1`

```solidity
//L1Transmitter.sol
function _executeUpdate() private {
    // ...
    uint256 toWithdraw = queuedWithdrawals > canWithdraw ? canWithdraw : queuedWithdrawals;
    if (toWithdraw > minWithdrawalThreshold) { //@audit only when amount > min withdrawal
        l1Strategy.withdraw(toWithdraw); //@audit actual amount withdrawn is toWithdraw
        // ... (withdrawal logic)
    }

    Client.EVM2AnyMessage memory evm2AnyMessage = _buildCCIPUpdateMessage(
        totalDeposits,
        claimedRewards + queuedWithdrawals,  // @audit This uses full queuedWithdrawals, not actual withdrawn amount
        depositsSinceLastUpdate,
        opRewardReceivers,
        opRewardAmounts
    );
    // ...
}
```

In L2Transmitter.sol, the inflated withdrawal amount (`tokensInTransitFromL1`) is accepted without validation:

```solidity
//L2Transmitter.sol
function _ccipReceive(Client.Any2EVMMessage memory _message) internal override {
    // ...
    (
        uint256 totalDeposits,
        uint256 tokensInTransitFromL1,
        uint256 tokensReceivedAtL1,
        address[] memory opRewardReceivers,
        uint256[] memory opRewardAmounts
    ) = abi.decode(_message.data, (uint256, uint256, uint256, address[], uint256[]));

    l2Strategy.handleUpdateFromL1(
        totalDeposits,
        tokensInTransitFromL1,  //@audit This value could be inflated
        tokensReceivedAtL1,
        opRewardReceivers,
        opRewardAmounts
    );
    // ...
}
```

3. In L2Strategy.sol, the inflated tokensInTransitFromL1 inflates deposit change calculations:
```solidity
function getDepositChange() public view returns (int) {
    return
        int256(
            l1TotalDeposits +
                tokensInTransitToL1 +
                tokensInTransitFromL1 +  //@audit This value could be inflated
                token.balanceOf(address(this))
        ) - int256(totalDeposits);
}
```
4. Finally, in StakingPool.sol, the inflated deposit change leads to an artificial increase in totalRewards and share price:
```solidity
function _updateStrategyRewards(uint256[] memory _strategyIdxs, bytes memory _data) private {
    int256 totalRewards;
    // ...
    for (uint256 i = 0; i < _strategyIdxs.length; ++i) {
        IStrategy strategy = IStrategy(strategies[_strategyIdxs[i]]);
        (int256 depositChange, , ) = strategy.updateDeposits(_data);
        totalRewards += depositChange;
    }

    if (totalRewards != 0) {
        totalStaked = uint256(int256(totalStaked) + totalRewards);
    }
    // ...
}
```
This vulnerability leads to an inflate share price of the liquid staking token.

## Proof of Concept

no poc

## Recommendation

Ensure accurate tracking of actual withdrawn amounts on L1:

```solidity
uint256 actualWithdrawn = 0;
if (toWithdraw > minWithdrawalThreshold) {
    l1Strategy.withdraw(toWithdraw);
    actualWithdrawn = toWithdraw;
    // ... (rest of withdrawal logic)
}
```
Use the actual withdrawn amount in the CCIP message to L2:
```solidity
Client.EVM2AnyMessage memory evm2AnyMessage = _buildCCIPUpdateMessage(
    totalDeposits,
    claimedRewards + actualWithdrawn,
    depositsSinceLastUpdate,
    opRewardReceivers,
    opRewardAmounts
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch between the L1 transmitter and the L2 receiver in the cross‑chain staking system. When a withdrawal is requested, the L1 contract calculates the actual amount that can be taken (toWithdraw) based on the available balance (canWithdraw). However, the CCIP message that is sent to L2 reports the full queuedWithdrawals amount instead of the actual toWithdraw value. As a result, the L2 transmitter records an inflated tokensInTransitFromL1 value, which is later added to the deposit change calculation in the L2 strategy. This inflated figure propagates to the staking pool’s reward update logic, causing the totalRewards variable to be larger than it should be and consequently raising the share price of the liquid staking token. The bug can be triggered whenever queuedWithdrawals exceeds the amount that can actually be withdrawn on L1, a condition that can occur during periods of high demand or when the strategy’s liquidity is insufficient. Users see the symptom of a higher token price or larger apparent rewards, but the underlying assets have not increased; balances may appear correct while the protocol’s accounting shows extra rewards that can be claimed. The issue was discovered during a manual audit of the L1Transmitter::_executeUpdate function, where the auditor noticed that the CCIP payload used claimedRewards + queuedWithdrawals instead of the real withdrawn amount. Because the inflated value is accepted on L2 without validation, the problem is subtle and may not be evident from normal transaction logs, making it hard to detect without deep inspection of cross‑chain messages. The vulnerability belongs to the class of “cross‑chain accounting mismatch” or “inflated state propagation” bugs, where one chain reports an incorrect state that other chains trust. To remediate, the contract should track the exact amount withdrawn on L1 and use that value when constructing the CCIP update message, and the L2 side should validate that the tokensInTransitFromL1 does not exceed the amount actually transferred. Fixing the bug restores the invariant that totalDeposits on L1 plus tokens in transit equals the sum of deposits recorded on L2, preventing artificial inflation of rewards and protecting users from receiving phantom gains.
