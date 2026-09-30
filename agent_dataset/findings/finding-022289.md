---
id: 22289
severity: "High"
---

# Anyone can call `StrategySupplyBase.harvest`, allowing users to avoid paying performance fees on interest

## Description

```solidity
Since `StrategySupplyBase.harvest` can be called by anyone, users can front-run the `rebalance` call or regularly call harvest to avoid paying protocol fees on interest. This allows users to receive more interest than they should.
```

## Proof of Concept

When there are profits in the Strategy, the administrator calls `rebalance` to settle protocol fees(performance fee). This calls `Strategy.harvest` to update the total deployed asset amount including interest and returns the amount of newly generated interest. Then `n%` of the interest is taken as protocol fees.
```solidity
function _harvestAndMintFees() internal {
    uint256 currentPosition = _totalAssets();
    if (currentPosition == 0) {
        return;
    }
    int256 balanceChange = _harvest();
    if (balanceChange > 0) {
        address feeReceiver = getFeeReceiver();
        uint256 performanceFee = getPerformanceFee();
        if (feeReceiver != address(this) && feeReceiver != address(0) && performanceFee > 0) {
            uint256 feeInEth = uint256(balanceChange) * performanceFee;
            uint256 sharesToMint = feeInEth.mulDivUp(totalSupply(), currentPosition * PERCENTAGE_PRECISION);
            _mint(feeReceiver, sharesToMint);
        }
    }
}

function _harvest() internal virtual override returns (int256 balanceChange) {
    return _strategy.harvest(); // Calls the harvest function of the strategy
}
```
However, `StrategySupplyBase.harvest` can be called by anyone. By front-running the `rebalance` request or regularly calling this function, users can avoid paying protocol fees on interest. This allows users to receive more interest than they should.
```solidity
function harvest() external returns (int256 balanceChange) {
    // Get Balance
    uint256 newBalance = getBalance();

    balanceChange = int256(newBalance) - int256(_deployedAmount);

    if (balanceChange > 0) {
        emit StrategyProfit(uint256(balanceChange));
    } else if (balanceChange < 0) {
        emit StrategyLoss(uint256(-balanceChange));
    }
    if (balanceChange != 0) {
        emit StrategyAmountUpdate(newBalance);
    }
    _deployedAmount = newBalance;
}
```
This is PoC. It demonstrates that anyone can call `StrategySupplyBase.harvest`. This can be run by adding it to the `StrategySupplyAAVEv3.ts` file.
```solidity
it('PoC - anyone can call harvest', async () => {
  const { owner, strategySupply, stETH, aave3Pool, otherAccount } = await loadFixture(
    deployStrategySupplyFixture,
  );
  const deployAmount = ethers.parseEther('10');
  await stETH.approve(await strategySupply.getAddress(), deployAmount);
  await strategySupply.deploy(deployAmount);

  //artificial profit
  await aave3Pool.mintAtokensArbitrarily(await strategySupply.getAddress(), deployAmount);

  await expect(strategySupply.connect(otherAccount).harvest())
    .to.emit(strategySupply, 'StrategyProfit')
    .to.emit(strategySupply, 'StrategyAmountUpdate');
});
```

## Recommendation

Add the `onlyOwner` modifier to `StrategySupplyBase.harvest` to restrict access.

**chefkenji (BakerFi) confirmed**

[PR-15](https://github.com/baker-fi/bakerfi-contracts/pull/15)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an improper access‑control flaw in the strategy contract where the public harvest function can be invoked by any address. Harvest is responsible for reconciling the strategy’s balance, emitting profit or loss events and updating the internal deployed amount. Because the function is not restricted to the contract owner or a privileged role, an external user can call it at any time, especially just before the protocol’s rebalance routine that calculates performance fees. The root cause is the missing onlyOwner (or similar) modifier on harvest, which allows the accounting state to be altered outside the intended fee‑collection flow. An attacker can exploit this by monitoring when the strategy has generated interest, then front‑running the scheduled rebalance transaction and calling harvest first. Harvest updates the internal balance to include the newly earned interest, which means that when the subsequent rebalance runs, the balance change reported to the fee‑minting logic is zero or reduced, causing the performance fee calculation to mint fewer (or no) fee shares. Consequently the protocol’s treasury receives less fee revenue while the attacker (or any user who called harvest) retains the full amount of interest. This situation occurs whenever there is accrued profit and the protocol relies on a separate rebalance call to trigger fee minting; any external account can intervene between profit accrual and fee collection. The affected parties are the protocol itself (lost revenue), its fee receiver, and indirectly all token holders who expect proper fee distribution. The issue was discovered during a Code4rena audit by reproducing the scenario in a test that called harvest from a non‑owner account and observed that the fee‑minting step received a zero balance change. The bug is subtle because harvest only emits events and updates a private variable, so the lack of access control does not raise an immediate alarm, and the fee logic lives in a different function, making the race condition easy to overlook. To remediate, harvest should be protected with an onlyOwner (or similar) modifier, or made internal so that only the authorized rebalance routine can invoke it, thereby preserving the intended accounting sequence. In user‑facing terms, a participant may notice that their yield appears higher than expected while the protocol’s fee balance stays unchanged, effectively meaning “money disappears from the treasury” and “extra interest shows up in my account”. This class of bug falls under unauthorized state‑change and fee‑evasion due to missing access control, leading to accounting inconsistencies and revenue loss.
