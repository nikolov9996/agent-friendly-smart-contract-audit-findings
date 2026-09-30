---
id: 15451
severity: "High"
---

# Not Update Rewards in `handleIncomingUpdate` Function of `SDLPoolPrimary` Leads to Incorrect Reward Calculations

## Description

Failing to update rewards before executing the handleIncomingUpdate function in SDLPoolPrimary, while adjusting the effectiveBalance of the ccipController, results in miscalculated rewards. This oversight can obstruct the distribution of rewards for the secondary chain.
Actions taken in the secondary pool are queued and then communicated to the primary pool. The primary pool must acknowledge these changes before they are executed. The message sent to the primary pool includes the number of new queued locks to be minted (numNewQueuedLocks) and the change in the reSDL supply (reSDLSupplyChange).
Upon receiving the message, the SDLPoolCCIPControllerPrimary  contract updates the reSDLSupplyByChain and forwards the message to SDLPoolPrimary. The SDLPoolPrimary contract then processes the message, returning the mintStartIndex for the secondary chain to use when minting new locks. It also updates the effectiveBalances  for the ccipController and the totalEffectiveBalance.

```solidity
  function ccipReceive(Client.Any2EVMMessage memory message) internal override {
        uint64 sourceChainSelector = _message.sourceChainSelector;

        (uint256 numNewRESDLTokens, int256 totalRESDLSupplyChange) = abi.decode(_message.data, (uint256, int256));

        if (totalRESDLSupplyChange > 0) {
            reSDLSupplyByChain[sourceChainSelector] += uint256(totalRESDLSupplyChange);
        } else if (totalRESDLSupplyChange < 0) {
            reSDLSupplyByChain[sourceChainSelector] -= uint256(-1 * totalRESDLSupplyChange);
        }
        uint256 mintStartIndex = ISDLPoolPrimary(sdlPool).handleIncomingUpdate(numNewRESDLTokens, totalRESDLSupplyChange);   
        _ccipSendUpdate(sourceChainSelector, mintStartIndex);

        emit MessageReceived(_message.messageId, sourceChainSelector);
    }
```
The issue arises because the handleIncomingUpdate function does not update the rewards before altering these values. Since these values directly affect reward accounting, failing to update them leads to incorrect calculations. This could result in a scenario where the total rewards accrued by all stakers exceed the available balance in the rewardsPool.

```solidity
  function handleIncomingUpdate(uint256 numNewRESDLTokens, int256 totalRESDLSupplyChange)
        external
        onlyCCIPController
        returns (uint256)
    {
       // some code ...

        if (_totalRESDLSupplyChange > 0) {
            effectiveBalances[ccipController] += uint256(_totalRESDLSupplyChange);
            totalEffectiveBalance += uint256(_totalRESDLSupplyChange);
        } else if (_totalRESDLSupplyChange < 0) {
            effectiveBalances[ccipController] -= uint256(-1 * _totalRESDLSupplyChange);
            totalEffectiveBalance -= uint256(-1 * _totalRESDLSupplyChange);
        }
  // more code ....
    }
```
For example, consider Alice has staked 500 sdl tokens, and there is an outgoing 1000 reSdl. The state would be as follows:
effectiveBalance[alice] = 500
effectiveBalance[ccipController] = 1000
totalEffectiveBalance = 1500
Now, assume 1500 reward tokens are distributed this will update the rewardPerToken = 1 (rewards/totalStaked), and Alice will withdraw her rewards. The amount of rewards Alice receives is calculated using the withdrawableRewards function, which relies on her effectiveBalance (controller.staked()). With a rewardPerToken of 1 and Alice's userRewardPerTokenPaid at 0, Alice would receive 500 rewards.

```solidity
   function withdrawableRewards(address _account) public view virtual returns (uint256) {
        return (controller.staked(account) * (rewardPerToken - userRewardPerTokenPaid[account])) / 1e18 + userRewards[_account];
    }
```
now, someone stakes another 1000 sdl on the secondary chain, an incoming update with a supply change of 1000 is received on the primary chain. This update changes the effectiveBalance[ccipController] to 2000 without a prior reward update which will keep the userRewardPerTokenPaid for ccipController 0. 

```solidity
     function handleIncomingUpdate(uint256 numNewRESDLTokens, int256 totalRESDLSupplyChange) external onlyCCIPController returns (uint256){
        uint256 mintStartIndex;
        if (_numNewRESDLTokens != 0) {
            mintStartIndex = lastLockId + 1;
            lastLockId += _numNewRESDLTokens;
        }

        if (_totalRESDLSupplyChange > 0) {
            effectiveBalances[ccipController] += uint256(_totalRESDLSupplyChange);
            totalEffectiveBalance += uint256(_totalRESDLSupplyChange);
        } else if (_totalRESDLSupplyChange < 0) {
            effectiveBalances[ccipController] -= uint256(-1 * _totalRESDLSupplyChange);
            totalEffectiveBalance -= uint256(-1 * _totalRESDLSupplyChange);
        }

        emit IncomingUpdate(numNewRESDLTokens, totalRESDLSupplyChange, mintStartIndex);

        return mintStartIndex;
    }
```
Consequently, when the RewardsInitiator contract calls the distributeRewards function in SDLPoolCCIPControllerPrimary, attempting to withdrawRewards from the rewardPool the call will perpetually fail. The rewards for the ccipController would be calculated as 2000 * (1 - 0) = 2000 rewards, while the actual balance of the rewardsPool is only 1000 rewards.

```solidity
     function distributeRewards() external onlyRewardsInitiator {
        uint256 totalRESDL = ISDLPoolPrimary(sdlPool).effectiveBalanceOf(address(this));
        address[] memory tokens = ISDLPoolPrimary(sdlPool).supportedTokens();
        uint256 numDestinations = whitelistedChains.length;

        ISDLPoolPrimary(sdlPool).withdrawRewards(tokens);
        // ... more code ..
    }
```
notice that the increase of 1000 will never be solved .

Incorrect reward calculations could  prevent rightful stakers from receiving their due rewards or leave unclaimable rewards in the pool (in the case of negative supply change), thereby compromising the protocol's credibility.

## Proof of Concept

here a poc that shows , that not updating reward in incomingUpdates , will cause the distributeReward function to revert , cause of insufficient balance in the reward pool , i used the repo setup : 

```typescript
 import { ethers } from 'hardhat'
import {  expect } from 'chai'
import { toEther, deploy, deployUpgradeable, getAccounts, fromEther } from '../../utils/helpers'
import {
  ERC677,
  CCIPOnRampMock,
  CCIPOffRampMock,
  CCIPTokenPoolMock,
  SDLPoolPrimary,
  SDLPoolCCIPControllerPrimary,
  Router,
} from '../../../typechain-types'
import {  Signer } from 'ethers'

describe('SDLPoolCCIPControllerPrimary', () => {
  let linkToken: ERC677
  let sdlToken: ERC677
  let token1: ERC677
  let token2: ERC677
  let controller: SDLPoolCCIPControllerPrimary
  let sdlPool: SDLPoolPrimary
  let onRamp: CCIPOnRampMock
  let offRamp: CCIPOffRampMock
  let tokenPool: CCIPTokenPoolMock
  let tokenPool2: CCIPTokenPoolMock
  let router: any
  let accounts: string[]
  let signers: Signer[]

  before(async () => {
    ;({ signers, accounts } = await getAccounts())
  })

  beforeEach(async () => {
    linkToken = (await deploy('ERC677', ['Chainlink', 'LINK', 1000000000])) as ERC677
    sdlToken = (await deploy('ERC677', ['SDL', 'SDL', 1000000000])) as ERC677
    token1 = (await deploy('ERC677', ['2', '2', 1000000000])) as ERC677
    token2 = (await deploy('ERC677', ['2', '2', 1000000000])) as ERC677

    const armProxy = await deploy('CCIPArmProxyMock')
    router = (await deploy('Router', [accounts[0], armProxy.address])) as Router
    tokenPool = (await deploy('CCIPTokenPoolMock', [token1.address])) as CCIPTokenPoolMock
    tokenPool2 = (await deploy('CCIPTokenPoolMock', [token2.address])) as CCIPTokenPoolMock
    onRamp = (await deploy('CCIPOnRampMock', [
      [token1.address, token2.address],
      [tokenPool.address, tokenPool2.address],
      linkToken.address,
    ])) as CCIPOnRampMock
    offRamp = (await deploy('CCIPOffRampMock', [
      router.address,
      [token1.address, token2.address],
      [tokenPool.address, tokenPool2.address],
    ])) as CCIPOffRampMock

    await router.applyRampUpdates([[77, onRamp.address]], [], [[77, offRamp.address]])

    let boostController = await deploy('LinearBoostController', [4 * 365 * 86400, 4])
    sdlPool = (await deployUpgradeable('SDLPoolPrimary', [
      'reSDL',
      'reSDL',
      sdlToken.address,
      boostController.address,
    ])) as SDLPoolPrimary
    controller = (await deploy('SDLPoolCCIPControllerPrimary', [
      router.address,
      linkToken.address,
      sdlToken.address,
      sdlPool.address,
      toEther(10),
    ])) as SDLPoolCCIPControllerPrimary

    await linkToken.transfer(controller.address, toEther(100))
    await sdlToken.transfer(accounts[1], toEther(200))
    await sdlPool.setCCIPController(controller.address)
    await controller.setRESDLTokenBridge(accounts[5])
    await controller.setRewardsInitiator(accounts[0])
    await controller.addWhitelistedChain(77, accounts[4], '0x11', '0x22')
  })

  it('poc that when there is encoming updates the rewared is wrong calculated',async () => {
      let wToken = await deploy('WrappedSDTokenMock', [token1.address])
      let rewardsPool = await deploy('RewardsPoolWSD', [
        sdlPool.address,
        token1.address,
        wToken.address,
      ])
      let wtokenPool = (await deploy('CCIPTokenPoolMock', [wToken.address])) as CCIPTokenPoolMock
      await sdlPool.addToken(token1.address, rewardsPool.address)
      await controller.approveRewardTokens([wToken.address])
      await controller.setWrappedRewardToken(token1.address, wToken.address)
      await onRamp.setTokenPool(wToken.address, wtokenPool.address)
      await offRamp.setTokenPool(wToken.address, wtokenPool.address)
      //1.user stakes : 
      await sdlToken.transferAndCall(sdlPool.address,toEther(1000),ethers.utils.defaultAbiCoder.encode(['uint256', 'uint64'], [0, 0]))
      //2.distrubute rewared : 
      await token1.transferAndCall(sdlPool.address, toEther(1000), '0x')
      //3. @audit incoming updates from secondary chain with 1000 resdl in supplychange : 
      await offRamp.connect(signers[4]).executeSingleMessage(
         ethers.utils.formatBytes32String('messageId'),
        77,
        ethers.utils.defaultAbiCoder.encode(['uint256','int256'], [3,toEther(1000)]),
        controller.address,
        []
      )
      // here the error : the sum of withdrawable rewards , will be more then the availabel reward balance in rewardPool . 
      let user = await sdlPool.withdrawableRewards(accounts[0])
      let wr = await sdlPool.withdrawableRewards(controller.address)
      let rewardsAvailable = (await rewardsPool.totalRewards())
      // since not user withdrew reward nor ccipController , the total rewareds should be greater or equal the total withdrawAble rewards , but this not the case : 
      expect(fromEther((wr[0].add(user[0])))).greaterThan(fromEther(rewardsAvailable))
      // now when the staker withdraw rewards the remain rewards will be not enough for ccipController : 
      await sdlPool.withdrawRewards([token1.address]);
      // distributing rewards will revert, since there is not enough balance to cover the ccipController rewards :
      await expect(controller.distributeRewards())
      .to.be.revertedWith('');
   })
})
```

## Recommendation

No data

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reward‑accounting error that occurs when the primary pool contract processes an incoming update from a secondary chain but fails to update the pending rewards before adjusting the effective balance of the cross‑chain controller. The root cause is that the handleIncomingUpdate function modifies the effectiveBalances mapping and totalEffectiveBalance for the CCIP controller without first invoking the internal reward‑update routine that would recalculate rewardPerToken based on the current totalEffectiveBalance. Because rewardPerToken is derived from the ratio of total rewards to totalEffectiveBalance, changing the balance without a prior reward snapshot inflates the controller’s share of future rewards. An attacker or any participant can trigger the bug simply by causing a supply change on the secondary chain – for example, by staking additional tokens on the secondary side – which results in a positive totalRESDLSupplyChange being forwarded to the primary pool. When the primary pool receives this message, it adds the supply change to the controller’s effective balance while leaving the stored rewardPerToken unchanged. Consequently, the next call to distributeRewards calculates a controller reward that exceeds the actual token balance held in the rewardsPool. Users experience this as missing or unclaimable rewards: the UI may show a positive withdrawableRewards amount for the controller, but the withdraw operation reverts due to insufficient pool balance, and legitimate stakers receive less than expected or see their reward claim fail. The issue manifests whenever an incoming update with a non‑zero supply change is processed, which is a normal operation in the cross‑chain staking flow, affecting all stakers and the protocol’s reward distribution logic. It was discovered during a functional test that simulated cross‑chain messages; the test observed that after an incoming update the sum of withdrawable rewards for the controller and a regular staker exceeded the total rewards held in the rewardsPool, causing the distributeRewards call to revert. The bug is subtle because the contract’s state variables appear to be updated correctly, and the reward calculation code is otherwise sound; the missing call to update rewards is easy to overlook in a complex cross‑chain flow. To remediate, the handleIncomingUpdate function should invoke the reward‑update routine (e.g., updateReward or similar) before mutating effectiveBalances, ensuring that rewardPerToken is recomputed with the old balance and that the controller’s accrued rewards are settled prior to the balance change. This aligns the accounting with the intended invariant that total rewards never exceed the pool balance and restores correct reward distribution for all participants.
