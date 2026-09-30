---
id: 4994
severity: "High"
---

# It is impossible to claim rewards in zlrewardscontroller.sol Submitted by osmanozdemir1, also found by Federico Bianucci, Sujith Somraaj, jovi.eth, 0xhashiman, tnch, bin2chen, elhaj, Chinmay Farkya, pauleth, Naveen Kumar J - 1nc0gn170, waﬄemakr, 0xarno and shaka

## Description

```solidity
function claim(
address _user,
address[] memory _tokens
) public whenNotPaused {
// SKIPPED FOR BREVITY
_vestTokens(_user, pending);
}
```
The claim function performs some checks and actions (calculates reward debt and user pending reward etc), and then calls the _vestTokens function.
```solidity
function _vestTokens(address _user, uint256 _amount) internal {
if (_amount == 0) revert NothingToVest();
streamedVesting.createVestFor(_user, _amount); //@audit-issue streamedVesting contract will try to burn vestedTokens from this contract. This contract never approved the StreamedVesting contract
}
```
The _vestTokens function then will call the streamedVesting.createVestFor function, which uses the msg.sender as the from address, and the msg.sender is the ZLRewardsController contract.
```solidity
function createVestFor(address to, uint256 amount) external whenNotPaused {
_createVest(msg.sender, to, amount); //@audit msg.sender is ZLRewardsController contract
}
```
```solidity
function _createVest(
address from,
address to,
uint256 amount
) internal whenNotPaused {
vestedToken.burnFrom(from, amount); //@audit-issue "from" is ZLRewardsController contract. That contract is never approved StreamedVesting as "spender"
lastId++;
// SKIPPED FOR BREVITY
}
```
As we can see above, the first step during the _createVest function is burning vestedTokens from the "from" address (which is ZLRewardsController) with this line: vestedToken.burnFrom(from, amount); vestedToken is an ERC20Burnable, and let's check the burnFrom function in the OpenZeppelin implementation:
```solidity
function burnFrom(address account, uint256 value) public virtual {
_spendAllowance(account, _msgSender(), value);
_burn(account, value);
}
```
As we can see here, it requires allowance. ZLRewardsControoler.claim() will always revert with ERC20InsufficientAllowance error. ZLRewardsController contract MUST approve the StreamedVesting contract as spender for this claim functionality to work. Similar approvals are made in this protocol at StreamedVesting.sol#L56 (streamedVesting approves the ZeroLocker contract as spender) and at BonusPool.sol#L24 (bonusPool approves the streamedVesting contract as spender) during initialization. Likelihood is high as it will always happen. Impact is high since this is one of the core functions and the reward mechanism of the protocol is totally broken, which makes it a critical issue.

## Proof of Concept

Before running the test we need to do a slight change in the protocol's fixture. We are going to change the pool configurator to make testing easier. Perform the change below in the test/fixtures/core.ts test file:
```solidity
await zLRewardsController.initialize(
    owner.address, // address _poolConfigurator,
    vesting.target, // IStreamedVesting _streamedVesting,
    locker.target, // IZeroLocker _locker,
    1000, // uint256 _rewardsPerSecond,
    token.target, // address _rdntToken,
    0 // uint256 _endingTimeCadence
);
```
After changing these lines, do the following steps:
• Create an empty file in the test folder and name it something.ts.
• Copy and paste the snippet below into the newly created file.
• Run it with npx hardhat test --grep "Always reverts when claiming".
```javascript
import { expect } from "chai";
import { ethers } from "hardhat";
import {
loadFixture,
time,
} from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { e18, deployCore as fixture } from "./fixtures/core";
describe("RewardsController", () => {
it("Always reverts when claiming", async function () {
const {
token: rewardToken,
vestedToken,
owner,
zLRewardsController,
otherAccount: user,
} = await loadFixture(fixture);
// First, transfer some vestedToken token to zlRewardsController address.
// StreamedVesting contract will try to burn them from "zlRewardsController" during claim.
await vestedToken.transfer(zLRewardsController, e18 * 100000000n);
// Configurator adds pool to the contract (configurator is owner).
// Note: I used regular token as rewardToken here instead of deploying a new mock token to make testing easier.
await zLRewardsController.connect(owner).addPool(rewardToken, e18 * 100000n);
expect(await zLRewardsController.poolLength()).eq(1);
// Owner registers reward deposit and starts.
await zLRewardsController.connect(owner).registerRewardDeposit(e18 * 100000000n);
await zLRewardsController.connect(owner).start();
// Transfer some reward tokens to user and register the user. "afterLockUpdate" function will register the user
await rewardToken.transfer(user.address, e18 * 100n);
await zLRewardsController.afterLockUpdate(user.address);
// fast forward time
await time.increase(86400 * 30 * 3);
// Check user's pending reward
const pendingReward = await zLRewardsController.allPendingRewards(user.address);
expect(pendingReward).greaterThan(0);
console.log("pend: ", pendingReward);
// ----------------------ACTION----------------
// User tries to claim.
// It will revert with insufficient allowance error
expect(zLRewardsController.connect(user).claimAll(user.address)).revertedWith("ERC20: insufficient allowance");
});
});
```

## Recommendation

Approve the streamedVesting contract as spender during initialize.
```solidity
// Inside the initialize
vestedToken.approve(address(steamedVesting), type(uint256).max)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the reward‑claiming workflow of the ZLRewardsController contract. When a user invokes the public claim function, the contract calculates the user’s pending reward and then forwards the amount to an internal _vestTokens routine. This routine calls StreamedVesting.createVestFor, which in turn invokes an internal _createVest function. The _createVest function attempts to burn the vested tokens from the address supplied as the "from" parameter by calling vestedToken.burnFrom(from, amount). Because StreamedVesting uses msg.sender as the source address, the "from" argument is the ZLRewardsController contract itself. The ERC20Burnable implementation of burnFrom first checks that the caller (StreamedVesting) has a sufficient allowance on the token contract to transfer the specified amount from the source address. However, ZLRewardsController never grants an allowance to the StreamedVesting contract for the vestedToken. Consequently, every call to claim triggers a revert with the OpenZeppelin ERC20InsufficientAllowance error. The root cause is a missing approval step during contract initialization, which violates the expected token‑spending relationship required for a burnFrom operation. The bug can be exploited trivially: any user attempting to claim accrued rewards will experience a transaction failure, receiving no tokens despite the protocol reporting a positive pending balance. From the user’s perspective the UI may display a non‑zero pending reward, but the claim button results in a reverted transaction and the user’s balance remains unchanged. This condition occurs whenever the claim function is executed after rewards have been accrued, i.e., under normal operation of the protocol’s reward distribution cycle. All participants who rely on the reward mechanism – token holders, liquidity providers, and any downstream contracts that expect vesting to occur – are affected because the core economic incentive is broken. The issue was discovered during a security audit and reproduced in automated tests that consistently reverted with the allowance error. It is hard to notice because the contract’s logic appears sound up to the point of vesting, and the failure only manifests at the token‑burn step, which is abstracted away behind an external contract call. The vulnerability belongs to the class of authorization bugs where a contract attempts to spend or burn tokens without having been granted the necessary allowance. To remediate the problem, the ZLRewardsController must approve the StreamedVesting contract as a spender for the vestedToken (typically with an unlimited allowance) during its initialization phase, ensuring that burnFrom can succeed and rewards can be vested and claimed as intended.
