---
id: 23598
severity: "High"
---

# [H-02]Reward token in GaugeFactoryCL can be drained by anyone

## Description

The GaugeFactoryCL.sol contract, responsible for creating GaugeCL instances for Algebra Concentrated Liquidity pools, has a public `createGauge` function. The implementation of the function is:

```solidity
function createGauge(address _rewardToken,address _ve,address _pool,address _distribution, address _internal_bribe, address _external_bribe, bool _isPair, 

                        IGaugeManager.FarmingParam memory farmingParam, address _bonusRewardToken) external returns (address) {


createEternalFarming(_pool, farmingParam.algebraEternalFarming, _rewardToken, _bonusRewardToken);

        last_gauge = address(new GaugeCL(_rewardToken,_ve,_pool,_distribution,_internal_bribe,_external_bribe,_isPair, farmingParam, _bonusRewardToken, address(this)));

        __gauges.push(last_gauge);

        return last_gauge;

    }
```

The `GaugeFactoryCL.createGauge` function lacks access control, allowing any external actor to call it. This function calls an internal `createEternalFarming` function whose implementation is:

```solidity
function createEternalFarming(address _pool, address _algebraEternalFarming, address _rewardToken, address _bonusRewardToken) internal {

    IAlgebraPool algebraPool = IAlgebraPool(_pool);

    uint24 tickSpacing = uint24(algebraPool.tickSpacing());

    address pluginAddress = algebraPool.plugin();        

    IncentiveKey memory incentivekey = getIncentiveKey(_rewardToken, _bonusRewardToken, _pool, _algebraEternalFarming);

    uint256 remainingTimeInCurrentEpoch = BlackTimeLibrary.epochNext(block.timestamp) - block.timestamp;

    uint128 reward = 1e10;

    uint128 rewardRate = uint128(reward/remainingTimeInCurrentEpoch);

    

    IERC20(_rewardToken).safeApprove(_algebraEternalFarming, reward);

    address customDeployer = IAlgebraPoolAPIStorage(algebraPoolAPIStorage).pairToDeployer(_pool);

    IAlgebraEternalFarming.IncentiveParams memory incentiveParams = 

        IAlgebraEternalFarming.IncentiveParams(reward, 0, rewardRate, 0, tickSpacing);

    IAlgebraEternalFarmingCustom(_algebraEternalFarming).createEternalFarming(incentivekey, incentiveParams, pluginAddress, customDeployer);

}
```

It seeds a new Algebra eternal farming incentive with a hard‑coded amount of `1e10` of the `_rewardToken`. It does this by approving the `algebraEternalFarming` contract, which then pulls these tokens from `GaugeFactoryCL`.

If the `GaugeFactoryCL` contract is pre‑funded with reward tokens, an attacker can repeatedly call `createGauge`, triggering `createEternalFarming` and causing the reward token to be transferred from `GaugeFactoryCL` to a new Algebra farm associated with a pool specified by the attacker, ultimately draining the reward token from `GaugeFactoryCL`. The attacker can then stake an LP NFT into the newly created (spam) `GaugeCL` and claim the reward.

## Proof of Concept

Protocol admin pre‑funds `GaugeFactoryCL` with `5e10` of USDC (50,000).

Attacker calls `GaugeFactoryCL.createGauge()`:

```solidity
IGaugeFactoryCL(GFCL_ADDRESS).createGauge(

    USDC_ADDRESS,       // _rewardToken

    VE_ADDRESS,

    TARGET_POOL_ADDRESS,

    ATTACKER_ADDRESS,   // _distribution

    ATTACKER_ADDRESS,   // _internal_bribe

    ATTACKER_ADDRESS,   // _external_bribe

    true,               // _isPair

    farmingParams,      // including ALGEBRA_ETERNAL_FARMING_ADDRESS

    ZERO_ADDRESS        // _bonusRewardToken

);
```

The public `createGauge` function is entered which calls its internal `createEternalFarming(_pool, farmingParam.algebraEternalFarming, USDC_ADDRESS, _bonusRewardToken)`.

Execution within `GaugeFactoryCL.createEternalFarming`:

```solidity
function createEternalFarming(address _pool, address _algebraEternalFarming, address _rewardToken, address _bonusRewardToken) internal {

    // ...

    uint128 reward = 1e10; // 10,000 USDC

    // ...

    // GaugeFactoryCL approves AlgebraEternalFarming to spend its USDC

    IERC20(_rewardToken /* USDC_ADDRESS */).safeApprove(_algebraEternalFarming, reward);

    // ...

    // Call to AlgebraEternalFarming which will pull the approved USDC

    IAlgebraEternalFarmingCustom(_algebraEternalFarming).createEternalFarming(incentivekey, incentiveParamsWithReward, pluginAddress, customDeployer);

}
```

Execution within `AlgebraEternalFarming.createEternalFarming()`:

```solidity
/// @inheritdoc IAlgebraEternalFarming

function createEternalFarming(

    IncentiveKey memory key,

    IncentiveParams memory params,

    address plugin

) external override onlyIncentiveMaker returns (address virtualPool) {

    address connectedPlugin = key.pool.plugin();

    if (connectedPlugin != plugin || connectedPlugin == address(0)) revert pluginNotConnected();

    if (IFarmingPlugin(connectedPlugin).incentive() != address(0)) revert anotherFarmingIsActive();


    virtualPool = address(new EternalVirtualPool(address(this), connectedPlugin));

    IFarmingCenter(farmingCenter).connectVirtualPoolToPlugin(virtualPool, IFarmingPlugin(connectedPlugin));


    key.nonce = numOfIncentives++;

    incentiveKeys[address(key.pool)] = key;

    bytes32 incentiveId = IncentiveId.compute(key);

    Incentive storage newIncentive = incentives[incentiveId];


    (params.reward, params.bonusReward) = _receiveRewards(key, params.reward, params.bonusReward, newIncentive);

    if (params.reward == 0) revert zeroRewardAmount();


    unchecked {

      if (int256(uint256(params.minimalPositionWidth)) > (int256(TickMath.MAX_TICK) - int256(TickMath.MIN_TICK)))

        revert minimalPositionWidthTooWide();

    }

    newIncentive.virtualPoolAddress = virtualPool;

    newIncentive.minimalPositionWidth = params.minimalPositionWidth;

    newIncentive.pluginAddress = connectedPlugin;


    emit EternalFarmingCreated(

      key.rewardToken,

      key.bonusRewardToken,

      key.pool,

      virtualPool,

      key.nonce,

      params.reward,

      params.bonusReward,

      params.minimalPositionWidth

    );


    _addRewards(IAlgebraEternalVirtualPool(virtualPool), params.reward, params.bonusReward, incentiveId);

    _setRewardRates(IAlgebraEternalVirtualPool(virtualPool), params.rewardRate, params.bonusRewardRate, incentiveId);

}
```

`_receiveRewards` function:

```solidity
function _receiveRewards(

    IncentiveKey memory key,

    uint128 reward,

    uint128 bonusReward,

    Incentive storage incentive

) internal returns (uint128 receivedReward, uint128 receivedBonusReward) {

    if (!unlocked) revert reentrancyLock();

    unlocked = false; // reentrancy lock

    if (reward > 0) receivedReward = _receiveToken(key.rewardToken, reward);

    if (bonusReward > 0) receivedBonusReward = _receiveToken(key.bonusRewardToken, bonusReward);

    unlocked = true;


    (uint128 _totalRewardBefore, uint128 _bonusRewardBefore) = (incentive.totalReward, incentive.bonusReward);

    incentive.totalReward = _totalRewardBefore + receivedReward;

    incentive.bonusReward = _bonusRewardBefore + receivedBonusReward;

}
```

`_receiveToken` function:

```solidity
function _receiveToken(IERC20Minimal token, uint128 amount) private returns (uint128) {

    uint256 balanceBefore = _getBalanceOf(token);

    TransferHelper.safeTransferFrom(address(token), msg.sender, address(this), amount);

    uint256 balanceAfter = _getBalanceOf(token);

    require(balanceAfter > balanceBefore);

    unchecked {

      uint256 received = balanceAfter - balanceBefore;

      if (received > type(uint128).max) revert invalidTokenAmount();

      return (uint128(received));

    }

}
```

Result: `1e10` (10,000) USDC has been transferred to the new algebra farm. The attacker repeats steps to fully transfer `50,000` USDC out of the `GaugeFactoryCL` contract.

Attacker stakes relevant LP NFT into the spam gauges through `GaugeCL.deposit`:

```solidity
function deposit(uint256 tokenId) external nonReentrant isNotEmergency {

    require(msg.sender == nonfungiblePositionManager.ownerOf(tokenId));

    

    nonfungiblePositionManager.approveForFarming(tokenId, true, farmingParam.farmingCenter);


    (IERC20Minimal rewardTokenAdd, IERC20Minimal bonusRewardTokenAdd, IAlgebraPool pool, uint256 nonce) = 

            algebraEternalFarming.incentiveKeys(poolAddress);

    IncentiveKey memory incentivekey = IncentiveKey(rewardTokenAdd, bonusRewardTokenAdd, pool, nonce);

    farmingCenter.enterFarming(incentivekey, tokenId);

    emit Deposit(msg.sender, tokenId);

}
```

Attacker directly calls `AlgebraEternalFarming.claimReward` to claim the rewards:

```solidity
/// @inheritdoc IAlgebraEternalFarming

function claimReward(IERC20Minimal rewardToken, address to, uint256 amountRequested) external override returns (uint256 reward) {

    return _claimReward(rewardToken, msg.sender, to, amountRequested);

}


function _claimReward(IERC20Minimal rewardToken, address from, address to, uint256 amountRequested) internal returns (uint256 reward) {

    if (to == address(0)) revert claimToZeroAddress();

    mapping(IERC20Minimal => uint256) storage userRewards = rewards[from];

    reward = userRewards[rewardToken];


    if (amountRequested == 0 || amountRequested > reward) amountRequested = reward;


    if (amountRequested > 0) {

      unchecked {

        userRewards[rewardToken] = reward - amountRequested;

      }

      TransferHelper.safeTransfer(address(rewardToken), to, amountRequested);

      emit RewardClaimed(to, amountRequested, address(rewardToken), from);

    }

}
```

## Recommendation

Implement robust access control on the `GaugeFactoryCL.createGauge()` function, restricting its execution to authorized administrators or designated smart contracts, thereby preventing unauthorized calls.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An attacker can drain the reward token held by the GaugeFactoryCL contract because the public createGauge function has no access control. When createGauge is called it invokes an internal createEternalFarming routine that approves a fixed amount of 1e10 of the supplied reward token to an external AlgebraEternalFarming contract and then relies on that contract to pull the tokens. If the factory has been pre‑funded with reward tokens for legitimate gauge creation, any external address can repeatedly call createGauge with attacker‑controlled pool parameters, causing the factory to approve and lose 1e10 tokens each time. The attacker can then deploy a spam GaugeCL, deposit an LP NFT and claim the transferred rewards, effectively moving the tokens from the factory to their own address. The vulnerability occurs whenever the factory holds reward tokens and the function is invoked, regardless of the caller. The root cause is the missing access restriction on createGauge combined with a hard‑coded reward amount and an approve‑then‑pull pattern that trusts the external farming contract. Because the function appears to be a normal gauge‑creation entry point, the issue may not be obvious during casual testing and only manifests as missing balances or zero rewards for legitimate users. The impact is loss of funds from the factory, reduction of available rewards for honest participants, and potential erosion of trust in the protocol. The flaw was discovered during a security audit that reviewed the factory’s external interface. Mitigation requires restricting createGauge to authorized accounts or contracts (e.g., onlyOwner or role‑based access), removing the hard‑coded reward seeding, and using a safe transfer instead of an unchecked approve that allows arbitrary token extraction.
