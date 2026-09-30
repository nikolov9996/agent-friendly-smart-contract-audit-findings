---
id: 1553
severity: "High"
---

# deposit in `ConvexStakingWrapper` will most certainly revert

## Description

[ConvexStakingWrapper.sol#L94-L99](https://github.com/code-423n4/2022-02-concur/blob/main/contracts/ConvexStakingWrapper.sol#L94-L99)  

```solidity
address mainPool = IRewardStaking(convexBooster)
    .poolInfo(_pid)
    .crvRewards;
if (rewards[_pid].length == 0) {
    pids[IRewardStaking(convexBooster).poolInfo(_pid).lptoken] = _pid;
    convexPool[_pid] = mainPool;
```

`convexPool[_pid]` is set to `IRewardStaking(convexBooster).poolInfo(_pid).crvRewards;`

`crvRewards` is a `BaseRewardPool` like this one: <https://etherscan.io/address/0x8B55351ea358e5Eda371575B031ee24F462d503e#code>.

`BaseRewardPool` does not implement `poolInfo`

[ConvexStakingWrapper.sol#L238](https://github.com/code-423n4/2022-02-concur/blob/main/contracts/ConvexStakingWrapper.sol#L238)

```solidity
IRewardStaking(convexPool[_pid]).poolInfo(_pid).lptoken
```

Above line calls `poolInfo` of `crvRewards` which causes revert.

## Proof of Concept

no poc

## Recommendation

According to Booster’s code

<https://etherscan.io/address/0xF403C135812408BFbE8713b5A23a04b3D48AAE31#code>

```solidity
//deposit lp tokens and stake
function deposit(uint256 _pid, uint256 _amount, bool _stake) public returns(bool){
    require(!isShutdown,"shutdown");
    PoolInfo storage pool = poolInfo[_pid];
    require(pool.shutdown == false, "pool is closed");

    //send to proxy to stake
    address lptoken = pool.lptoken;
    IERC20(lptoken).safeTransferFrom(msg.sender, staker, _amount);
```

`convexBooster` requires `poolInfo[_pid].lptoken`.

change L238 to

```solidity
IRewardStaking(convexBooster).poolInfo(_pid).lptoken
```

The warden has shown how an improper assumption about the pool contract can cause reverts.

While the risk of loss of funds is non-existent because all calls will revert, I believe the core functionality of the code is broken. For that reason, I think High Severity to be the proper severity.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the ConvexStakingWrapper contract where it incorrectly assumes that the address stored in the mapping convexPool[_pid] implements the same interface as the Convex Booster contract. During initialization the wrapper records the address returned by IRewardStaking(convexBooster).poolInfo(_pid).crvRewards, which is a BaseRewardPool instance. Later, when a user attempts to deposit, the wrapper executes IRewardStaking(convexPool[_pid]).poolInfo(_pid).lptoken to retrieve the underlying LP token address. Because BaseRewardPool does not define a poolInfo function, the call resolves to a non‑existent function selector and the EVM reverts with an undefined function error. The root cause is an interface mismatch: the code treats a reward pool contract as if it were a booster pool contract, violating the contract’s abstraction boundaries. An attacker does not need to exploit the bug; any legitimate deposit transaction will trigger the faulty call and revert, making the deposit functionality unusable. From a user’s perspective, attempts to stake LP tokens result in a transaction that fails immediately, often accompanied by a generic “execution reverted” message, leaving the user with the impression that the platform is broken or possibly malicious. The condition under which the bug manifests is any call to the deposit function after the wrapper has stored a BaseRewardPool address, which is the default behavior after the contract is deployed. All participants who rely on the wrapper – LP providers, liquidity miners, and the protocol’s revenue distribution logic – are affected because the core accounting flow (deposit, stake, and reward collection) cannot proceed. The issue was discovered during a static code audit when the auditors inspected the initialization logic and noticed that the stored address was of a different contract type, then verified that subsequent calls would hit a missing function. The bug can be hard to notice because the Solidity compiler does not enforce that the target address actually implements the called interface; the mismatch only surfaces at runtime. To remediate the problem, the wrapper must reference the original Booster contract (convexBooster) when querying poolInfo, for example by replacing IRewardStaking(convexPool[_pid]).poolInfo(_pid) with IRewardStaking(convexBooster).poolInfo(_pid). This ensures that the correct contract, which implements poolInfo, is used to retrieve the LP token address. Conceptually, the fix restores the proper separation of responsibilities: the wrapper should store only the Booster pool identifier and use the Booster’s interface for all pool metadata, while keeping reward pool addresses for reward distribution only. By correcting the interface assumption, deposits will no longer revert, the UI will reflect successful staking, and the protocol’s intended accounting and reward flow will be restored.
