---
id: 4732
severity: "High"
---

# _recalep2pdbalance should be called before p2udtoken.burn/mint, not after Submitted by cccz

## Description

In DToken._beforeTokenTransfer, the Distributor.beforeTokenTransfer corresponding to that DToken is called, which will call Distributor._distribute to distribute the reward, thus ensuring that the reward can be correctly distributed before the balance is updated:
```solidity
function _beforeTokenTransfer(
    address from_,
    address to_,
    uint256 amount_
)
    internal
    virtual
    override
{
    uint i = 0;
    uint n = _totalDistributors;
    while (i < n) {
        _distributors[i].beforeTokenTransfer(from_, to_, amount_);
        i++;
    }
}
```
When distributing GOAT mining rewards, the rewards are first distributed to the pool based on the _eP2PDToken balance, where they are distributed to users based on their p2UDtoken balance in the pool. And the user's p2UDtoken balance in the pool affects the pool's _eP2PDToken balance.

However, when stake ETH, p2UDtoken.mint is called first, which will increase the user's share in the pool, and then _eP2PDToken.mint is called in _reCalEP2PDBalance, which will claim the global GOAT mining reward, which will be distributed according to the user's balance after the mint, not before.

```solidity
p2UDtoken.mint(account_, powerMinted);
// ...
_reCalFs(poolOwner_);
// ...
function _reCalFs(
    address account_
)
    internal
{
    uint maxEarning = _eEarning.maxEarningOf(account_);
    _profileC.updateFsOf(account_, LHelper.calFs(
        _eEarning.balanceOf(account_) + _voting.defenderEarningFreezedOf(account_),
        maxEarning
    ));
    _reCalEP2PDBalance(account_);
}
// ...
function _reCalEP2PDBalance(
    address poolOwner_
)
    internal
{
    if (_poolFactory.isCreated(poolOwner_)) {
        IPoolFactory.SPool memory pool = _poolFactory.getPool(poolOwner_);
        IDToken p2UDtoken = IDToken(pool.dToken);
        uint oldEP2PBalance = _eP2PDToken.balanceOf(pool.dctDistributor);
        uint newEP2PBalance = LHelper.calEP2PDBalance(
            _profileC.fsOf(poolOwner_),
            _profileC.boosterOf(poolOwner_),
            p2UDtoken.totalSupply()
        );
        if (newEP2PBalance > oldEP2PBalance) {
            _eP2PDToken.mint(pool.dctDistributor, newEP2PBalance - oldEP2PBalance);
        } else if (newEP2PBalance < oldEP2PBalance) {
            _eP2PDToken.burn(pool.dctDistributor, oldEP2PBalance - newEP2PBalance);
        }
    }
}
```
Consider that there are currently 1000 global rewards to be distributed, poolA has 10% power and Alice has 50% of poolA. When Alice stake ETH to increase her share to 60%, the global reward will be distributed to Alice 60 instead of 50.

## Proof of Concept

no poc

## Recommendation

The fix would be to pull GOAT mining rewards before p2UDtoken.mint/burn.

- In lockWithdraw:
```solidity
if (isEth_) {
    require(restAmount == 0 || restAmount >= _minStakeETHAmount, "rest amount too small");
    IPoolFactory.SPool memory pool = _poolFactory.getPool(poolOwner_);
    IDToken p2UDtoken = IDToken(pool.dToken);
    uint burnedPower = LHelper.calBurnStakingPower(p2UDtoken.balanceOf(account), amount_, oldLockData.amount);
    _dP2PDistributor.distribute();
    _dP2PDistributor.claimFor(pool.dctDistributor, pool.dctDistributor);
    p2UDtoken.burn(account, burnedPower);
    _reCalEP2PDBalance(poolOwner_);
    LLido.allToEth(minEthA_);
    // _weth.withdraw(_weth.balanceOf(address(this)));
    dest_.transfer(address(this).balance);
```

- In _stake:
```solidity
powerMinted = LHelper.calMintStakingPower(
    oldLockData,
    aLock,
    duration_,
    account_ == poolOwner_,
    _selfStakeAdvantage
);
}
IPoolFactory.SPool memory pool = _poolFactory.getPool(poolOwner_);
IDToken p2UDtoken = IDToken(pool.dToken);
bool isFirstStake = p2UDtoken.totalSupply() == 0;
_dP2PDistributor.distribute();
_dP2PDistributor.claimFor(pool.dctDistributor, pool.dctDistributor);
p2UDtoken.mint(account_, powerMinted);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an ordering flaw in the reward distribution logic of a staking protocol that separates two token types: a pool‑share token (p2UDtoken) and a global reward token (eP2PDToken). The contract is supposed to distribute accumulated GOAT mining rewards to each pool based on the users' p2UDtoken balances before those balances are changed. In the current implementation, when a user stakes ETH, the contract first mints additional p2UDtoken to increase the user’s share, and only afterwards calls the internal function that recalculates and distributes the eP2PDToken rewards. Because the reward calculation uses the updated p2UDtoken total supply and the user’s new balance, the global reward pool is allocated as if the user already owned the larger share. Consequently, the user receives a proportion of the global reward that is higher than the proportion of power they actually contributed at the moment the reward was earned. This mis‑allocation can be observed when a user’s reward amount jumps from, for example, 50 % of the pool’s reward to 60 % after a single stake, even though the global reward pool has not changed. The impact is that the pool’s reward balance is drained faster than intended, other participants receive less than their fair share, and the protocol’s accounting assumptions about proportional distribution are violated. The bug manifests whenever p2UDtoken.mint or p2UDtoken.burn is executed before the distributor’s claim function is invoked, i.e., during staking, unstaking, or lock‑withdraw operations. It affects all participants in the affected pools, the protocol’s overall reward economics, and any downstream contracts that rely on correct reward accounting. The issue was discovered during a security audit by Spearbit, who noted that the reward distribution hook (_beforeTokenTransfer) is called before balance updates, but the higher‑level staking flow calls mint first and only later triggers the reward recalculation, breaking the intended order. The problem is subtle because the contract does emit reward events and the balances appear consistent on a per‑transaction basis; only a careful analysis of the sequence of state changes reveals the over‑allocation. To remediate, the protocol should pull (claim and distribute) the pending GOAT rewards before any p2UDtoken mint or burn operation, ensuring that the reward calculation always uses the pre‑action balances. This change restores the invariant that rewards are allocated based on the share of power held at the time of distribution, preventing users from receiving more than their entitled portion and preserving the integrity of the pool’s reward accounting.
