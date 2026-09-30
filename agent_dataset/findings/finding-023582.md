---
id: 23582
severity: "Critical"
---

# Validator and protocol fees can exceed 100 percent of rewards in PolygonStrategy.sol

## Description

The `setValidatorMEVRewardsPercentage` function in `PolygonStrategy.sol` allows setting the validator MEV rewards percentage up to 100% (10,000 basis points), but does not account for the total protocol fees (`_totalFeesBasisPoints`). This means the combined sum of all fees can exceed 100% of the rewards, leading to over-distribution of rewards. While `setValidatorMEVRewardsPercentage` only checks its own limit:

```solidity
function setValidatorMEVRewardsPercentage(
    uint256 _validatorMEVRewardsPercentage
) external onlyOwner {
    // @audit should consider the totalFeesBasisPoints.
    // updateDeposits will report more than it can pay in fees.
    if (_validatorMEVRewardsPercentage > 10000) revert FeesTooLarge();
    validatorMEVRewardsPercentage = _validatorMEVRewardsPercentage;
    emit SetValidatorMEVRewardsPercentage(_validatorMEVRewardsPercentage);
}
```

Notice the other fees have a limit of 30% in basis points:

```solidity
// updateFee
if (_totalFeesBasisPoints() > 3000) revert FeesTooLarge();
```

This separation allows the sum of `validatorMEVRewardsPercentage` and protocol fees to exceed 100% of the rewards, which can lead to an over‑minting scenario in `StakingPool.sol`:

```solidity
function updateDeposits(
    bytes calldata
)
    external
    onlyStakingPool
    returns (int256 depositChange, address[] memory receivers, uint256[] memory amounts)
{
    ...
    uint256 validatorMEVRewards = ((balance - totalQueued) *
        validatorMEVRewardsPercentage) / 10000;
    receivers = new address[](fees.length + (validatorMEVRewards != 0 ? 1 : 0));
    amounts = new uint256[](receivers.length);
    for (uint256 i = 0; i < fees.length; ++i) {
        receivers[i] = fees[i].receiver;
        amounts[i] = (uint256(depositChange) * fees[i].basisPoints) / 10000;
    }
    if (validatorMEVRewards != 0) {
        receivers[receivers.length - 1] = address(validatorMEVRewardsPool);
        amounts[amounts.length - 1] = validatorMEVRewards;
    }
    ...
}
```

The `StakingPool._updateStrategyRewards` logic then mints shares based on total fee amounts:

```solidity
uint256 sharesToMint = (totalFeeAmounts * totalShares) /
    (totalStaked - totalFeeAmounts);
_mintShares(address(this), sharesToMint);
```

**Example**
1. The owner sets `validatorMEVRewardsPercentage` to 100% (10,000 basis points).  
2. The protocol fee is 20% (2,000 basis points) via `_totalFeesBasisPoints`.  
3. The contract now has a combined fee rate of 120% (10,000 + 2,000 basis points).  
4. When 10 tokens are available as rewards, the `updateDeposits` reports to `StakingPool` logic 12 tokens to be minted.  
5. This results in the system issuing more tokens than it actually has, leading to over‑minting of shares in the pool.

Impact: protocol fees can exceed 100% of rewards.

## Proof of Concept

```ts
// In polygon-strategy.test.ts modify the strategy initialization to include 20% of fees:
const strategy = (await deployUpgradeable('PolygonStrategy', [
    token.target,
    stakingPool.target,
    stakeManager.target,
    7,
    vaultImp,
    2500,
    - [],
+   [
+       {
+           receiver: ethers.Wallet.createRandom().address,
+           basisPoints: 1000 // 10%
+       },
+       {
+           receiver: ethers.Wallet.createRandom().address,
+           basisPoints: 1000 // 10%
+       }
+   ],
])) as PolygonStrategy
```

```ts
describe.only('updateDeposits mint above 100%', () => {
    it('should cause stakingPool to overmint rewards', async () => {
        const { strategy, token, vaults, accounts, stakingPool, validatorShare, validatorShare2 } =
            await loadFixture(deployFixture)
        await strategy.setValidatorMEVRewardsPercentage(10000) // 100%
        // current fees is 20% for receivers + 100% for validator rewards
        await stakingPool.deposit(accounts[1], toEther(1000), ['0x'])
        await strategy.depositQueuedTokens([0, 1, 2], [toEther(10), toEther(20), toEther(30)])
        assert.equal(fromEther(await strategy.getTotalDeposits()), 1000)
        assert.equal(fromEther(await strategy.totalQueued()), 940)
        assert.equal(fromEther(await strategy.getDepositChange()), 0)
        // send 10 MATIC to strategy
        await token.transfer(strategy.target, toEther(10))
        assert.equal(fromEther(await strategy.getDepositChange()), 10)
        // @audit we will mint 120% of 10 instead of 100%
        // notice totalRewards is 10(depositChange),
        await expect(stakingPool.updateStrategyRewards([0], '0x'))
            .to.emit(stakingPool, "UpdateStrategyRewards")
            // totalRewards = strategy.depositChange
            // msg.sender, totalStaked, totalRewards, totalFeeAmounts
            .withArgs(accounts[0], toEther(1010), toEther(10), toEther(12));
    })
})
```

Output:
```
PolygonStrategy
updateDeposits mint above 100%
should cause stakingPool to overmint rewards (608ms)
1 passing (611ms)
```

## Recommendation

Recommended mitigation: when updating fees, check that total fees (MEV rewards + other fees) do not surpass 100%.

```solidity
function setValidatorMEVRewardsPercentage(
    uint256 _validatorMEVRewardsPercentage
) external onlyOwner {
    // if (_validatorMEVRewardsPercentage > 10000) revert FeesTooLarge();
    if (_validatorMEVRewardsPercentage + _totalFeesBasisPoints() > 10000) revert FeesTooLarge();
    validatorMEVRewardsPercentage = _validatorMEVRewardsPercentage;
    emit SetValidatorMEVRewardsPercentage(_validatorMEVRewardsPercentage);
}
```

```solidity
function addFee(address _receiver, uint256 _feeBasisPoints) external onlyOwner {
    _updateStrategyRewards();
    fees.push(Fee(_receiver, _feeBasisPoints));
    // if (_totalFeesBasisPoints() > 3000) revert FeesTooLarge();
    uint256 totalFees = _totalFeesBasisPoints();
    if (totalFees > 3000 || totalFees + validatorMEVRewardsPercentage > 10000) revert FeesTooLarge();
    emit AddFee(_receiver, _feeBasisPoints);
}
```

```solidity
function updateFee(
    uint256 _index,
    address _receiver,
    uint256 _feeBasisPoints
) external onlyOwner {
    _updateStrategyRewards();
    if (_feeBasisPoints == 0) {
        fees[_index] = fees[fees.length - 1];
        fees.pop();
    } else {
        fees[_index].receiver = _receiver;
        fees[_index].basisPoints = _feeBasisPoints;
    }
    // if (_totalFeesBasisPoints() > 3000) revert FeesTooLarge();
    uint256 totalFees = _totalFeesBasisPoints();
    if (totalFees > 3000 || totalFees + validatorMEVRewardsPercentage > 10000) revert FeesTooLarge();
    emit UpdateFee(_index, _receiver, _feeBasisPoints);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an over‑allocation of fees in the PolygonStrategy contract that allows the sum of validator MEV rewards and other protocol fees to exceed 100 % of the available rewards. The root cause is that the setValidatorMEVRewardsPercentage function only validates the validator fee against a 10,000‑basis‑point ceiling and does not incorporate the current protocol fee basis points when performing the check. Consequently, an owner can configure a validator fee of up to 100 % while protocol fees, which are limited separately to 30 %, remain non‑zero, resulting in a combined fee rate greater than the total reward pool. Exploitation occurs when the owner sets the validator fee to its maximum and retains any existing protocol fee; during the updateDeposits call the contract computes a validator reward amount based on the full reward balance and then adds the protocol fee amounts, producing a fee total that exceeds the actual reward amount. The StakingPool’s _updateStrategyRewards logic then mints new shares proportional to this inflated fee total, effectively creating more shares than the underlying tokens support. The impact is an inflation of the pool’s share supply, breaking the accounting invariants of the system, diluting existing holders, and potentially allowing the protocol to distribute more tokens than it holds, which can erode trust and value. This condition occurs whenever fee parameters are changed without a combined‑fee validation and when rewards are distributed through updateDeposits, affecting all participants: token holders, stakers, the validator reward pool, and the protocol itself. The issue was discovered during a security audit and reproduced with a test that set the validator fee to 100 % and added a 20 % protocol fee, causing the staking pool to report minting 120 % of the reward amount. The bug is subtle because each fee component individually respects its own limit, making the over‑allocation easy to miss in casual reviews. To fix the problem, the contract must enforce that the sum of validatorMEVRewardsPercentage and the total protocol fee basis points never exceeds 10,000, adding this combined check to the setter and to any function that modifies fee structures. This ensures that the total fee rate cannot surpass the reward pool, preserving correct minting logic and maintaining the integrity of the protocol’s financial model.
