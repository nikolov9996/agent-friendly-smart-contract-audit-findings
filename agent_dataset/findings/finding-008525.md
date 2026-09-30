---
id: 8525
severity: "High"
---

# User’s Staked ETH Can Be Stuck in the Protocol Through Two Cases

## Description

The deposit() function in the Portal.sol contract allows users to stake their ETH into any staking pool that is created. If the user wants to unstake his ETH he must make a withdrawal request to the WithdrawalContract.sol contract of the given staking pool by calling the enqueue() function. Note: When a staking pool is created, a separate contract is deployed for that staking pool called WithdrawalContract.sol. The impact is primarily financial, as the current implementation for enqueue() function in WithdrawalContract.sol compels users to initiate a withdrawal with a minimum of 0.05 ETH.

In contrast Portal.sol, the deposit() function lacks any restrictions on the amount of ETH that can be added to a staking pool. The following two scenarios show two Proof of Concepts of how user’s funds can be stuck in the protocol.

## Proof of Concept

Scenario 1  
```solidity
it("Alice's funds locked - first case", async function () {
// 1. CreatePool - The poolOwner creates a public pool
// 2. CreateOperator - The operatorOwner initiates the operator
// 3. Alice wants to stake 0.04 ETH in this public poll and
// she calls deposit() function , accordingly she will receive 0.04 gETH.
const aliceFirstDepositAmount = new BN(String(1e18)).muln(0.04); // 0.04 ETH
await this.Portal.deposit(publicPoolId, 0, [], 0, MAX_UINT256, aliceStaker, {
from: aliceStaker,
value: aliceFirstDepositAmount,
});
// 4. PoolOwner sees Alice's successful transaction and decides to change the visibility of the pool to private.
// this means that if a pool is not public , only the controller and the whitelisted addresses can deposit/stake.
await this.Portal.setPoolVisibility(publicPoolId, true, {
from: poolOwner,
});
// 5. Expect true to be executed as the pool is private.
expect(await this.Portal.isPrivatePool(publicPoolId)).to.be.equal(true);
// 6. Alice decides to unstake her 0.04 ETH from the "public pool" and
// she calls enqueue() function to queue a withdrawal request into the queue.
// Expect revert to be executed as the minimum size of the withdrawal request is 0.05 gETH.
await expectRevert(
this.WML.$enqueue(aliceFirstDepositAmount, "0x", aliceStaker, {
from: aliceStaker,
}),
// Actually it's 0.05 ETH (this issue is reported as Informational as well).
"WML:min 0.01 gETH"
);

// 7. Alice decides to deposit/stake another 0.01 ETH to make a total of 0.05 ETH because
// this is the minimum size for a withdrawal request.
// Expect revert to be executed because the poolOwner has changed visibility to private and
// only the controller and the whitelisted addresses can deposit/stake into the private pool.
// 8. Alice's staked funds of 0.04 ETH are locked in the private pool.
const aliceSecondDepositAmount = new BN(String(1e18)).muln(0.01); // 0.01 ETH
await expectRevert(
this.Portal.deposit(publicPoolId, 0, [], 0, MAX_UINT256, aliceStaker, {
from: aliceStaker,
value: aliceSecondDepositAmount,
}),
"SML:no whitelist"
);
});
```

Scenario 2  
```solidity
it("Alice's funds locked - second case", async function () {
// 1. CreatePool - The poolOwner creates a public pool
// 2. CreateOperator - The operatorOwner initiates the operator
// 3. Alice wants to stake 0.04 ETH in this public poll and
// she calls deposit() function , accordingly she will receive 0.04 gETH.
const aliceFirstDepositAmount = new BN(String(1e18)).muln(0.04); // 0.04 ETH
await this.Portal.deposit(publicPoolId, 0, [], 0, MAX_UINT256, aliceStaker, {
from: aliceStaker,
value: aliceFirstDepositAmount,
});
// 4. The Government decided to pause the Portal contact and accordingly ,
// the deposit() function is also paused because there is a whenNotPaused modifier
await this.Portal.pause();

// 5. Alice decides to unstake her 0.04 ETH from the public pool and
// she calls enqueue() function to queue a withdrawal request into a queue.
// Expect revert to be executed as the minimum size of the withdrawal request is 0.05 gETH.
await expectRevert(
this.WML.$enqueue(aliceFirstDepositAmount, "0x", aliceStaker, {
from: aliceStaker,
}),
// Actually it's 0.05 ETH (this issue is reported as Informational as well).
"WML:min 0.01 gETH"
);
// 6. Alice decides to deposit/stake another 0.01 ETH to make a total of 0.05 ETH because
// this is the minimum size for a withdrawal request.
// Expect revert to be executed because the deposit() function is paused.
// 7. Alice's staked funds of 0.04 ETH are locked in the public pool.
const aliceSecondDepositAmount = new BN(String(1e18)).muln(0.01); // 0.01 ETH
await expectRevert(
this.Portal.deposit(publicPoolId, 0, [], 0, MAX_UINT256, aliceStaker, {
from: aliceStaker,
value: aliceSecondDepositAmount,
}),
"Pausable: paused"
);
});
```

## Recommendation

To address this vulnerability, it is crucial to implement a check in the deposit() function for minimum deposit limit of 0.05 ETH or remove the check for the minimum size of the withdrawal request for enqueue() function.

Solution one:  
File: contracts/Portal/modules/StakeModule/libs/StakeModuleLib.sol#L1023  
```solidity
uint256 private constant _MIN_DEPOSIT_SIZE = 0.05 ether;
function deposit(
PooledStaking storage self,
DSML.IsolatedStorage storage DATASTORE,
uint256 poolId,
uint256 mingETH,
uint256 deadline,
address receiver
) external returns (uint256 boughtgETH, uint256 mintedgETH) {
_authenticate(DATASTORE, poolId, false, false, [false, true]);
require(msg.value >= _MIN_DEPOSIT_SIZE, "SML:min 0.05 ETH");
.
.
}
```

Solution two:  
File: contracts/Portal/modules/WithdrawalModule/libs/WithdrawalModuleLib.sol#L339  
```solidity
function _enqueue(
PooledWithdrawal storage self,
uint256 trigger,
uint256 size,
address owner
) internal {
require(size >= MIN_REQUEST_SIZE, "WML:min 0.01 gETH");
.
.
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract suite allows a user to stake ETH through a deposit() function that imposes no lower bound on the amount deposited, while the corresponding withdrawal mechanism requires a minimum request size of 0.05 ETH. This asymmetry creates a logical inconsistency: a staker who initially deposits less than 0.05 ETH can later be prevented from adding the missing amount because the pool may become private or the Portal contract may be paused, both of which block further deposits. In the first scenario the pool owner changes the pool visibility to private after the small deposit, so the user cannot increase the stake to meet the withdrawal threshold. In the second scenario the contract is paused, which also disables deposits. When the user subsequently attempts to enqueue a withdrawal, the call reverts with the minimum‑size error, and because the user cannot make an additional deposit, the originally staked ETH remains locked in the pool with no way to retrieve it. The impact is financial: the affected user’s funds are effectively frozen, and the protocol’s reputation suffers because users cannot rely on the ability to withdraw their stake. The vulnerability is discovered during a security audit that exercised edge‑case flows and observed the mismatch between deposit and withdrawal constraints. It is hard to notice in normal operation because the deposit succeeds and the UI may not warn that a later change in pool visibility or a pause will make the funds unrecoverable. The bug belongs to the class of “minimum‑withdrawal‑size mismatch” or “state‑dependent lock‑up” defects, where business logic assumes that users can always satisfy a minimum withdrawal amount, but protocol state changes invalidate that assumption. To remediate, the protocol should either enforce the same minimum deposit amount as the withdrawal request, remove the minimum‑withdrawal requirement, or adjust the visibility and pause logic to allow users to top‑up their stake after a pool becomes private or the contract is paused, thereby ensuring that funds can always be withdrawn according to the advertised rules.
