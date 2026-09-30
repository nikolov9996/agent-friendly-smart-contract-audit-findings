---
id: 23255
severity: "High"
---

# Liquidity provided when initializing collection cannot be withdrawn

## Description

UniswapImplementation.sol does not offer a way to withdraw the initial liquidity provided from the pool, causing the total loss of funds for any user who initializes a pool.
Interacting with Uniswap v4 requires a peripheral contract to unlock() the PoolManager, which then calls unlockCallback() on said peripheral contract. It is the job of unlockContract() to handle any interactions with PoolManager, including modifying liquidity. In UniswapImplementation.sol, the only time it ever calls unlock() on the PoolManager is once during initialization. After that, it is impossible for the Implementation contract to modify the liquidity of the Pool on behalf of the depositor.
Positions in PoolManager are credited to the contract that calls modifyLiquidity() on it. This means that the Implementation contract technically owns the liquidity provided by the user, and if the contract does not contain logic to withdraw funds on behalf of said user the funds are lost for good.
```solidity
function initializeCollection(address _collection, uint _amount0, uint _amount1, uint _amount1Slippage, uint160 _sqrtPriceX96) public override {
    // Ensure that only our {Locker} can call initialize
    if (msg.sender != address(locker)) revert CallerIsNotLocker();
    ...
    // Obtain the UV4 lock for the pool to pull in liquidity
    abi.encode(CallbackData({
        poolKey: poolKey,
        liquidityDelta: LiquidityAmounts.getLiquidityForAmounts({
            sqrtPriceX96: _sqrtPriceX96,
            sqrtPriceAX96: TICK_SQRT_PRICEAX96,
            sqrtPriceBX96: TICK_SQRT_PRICEBX96,
            amount0: poolParams.currencyFlipped ? _amount1 : _amount0,
            amount1: poolParams.currencyFlipped ? _amount0 : _amount1
        }),
        liquidityTokens: _amount1,
        liquidityTokenSlippage: _amount1Slippage
    })
));
}
```
```solidity
function _unlockCallback(bytes calldata _data) internal override returns (bytes memory) {
    ...
    // As this call should only come in when we are initializing our pool, we
    // don't need to worry about `take` calls, but only `settle` calls.
    modifyLiquidity(
        key: params.poolKey,
        params: IPoolManager.ModifyLiquidityParams({
            tickLower: MIN_USABLE_TICK,
            tickUpper: MAX_USABLE_TICK,
            liquidityDelta cast so that it can only ever be positive
            salt: ''
        }),
        hookData: ''
    );
}
```
This is in PoolManager.sol:
```solidity
function modifyLiquidity(
    PoolKey memory key,
    IPoolManager.ModifyLiquidityParams memory params,
    bytes calldata hookData
) external onlyWhenUnlocked noDelegateCall returns (BalanceDelta callerDelta, BalanceDelta feesAccrued) {
    BalanceDelta principalDelta;
    (principalDelta, feesAccrued) = pool.modifyLiquidity(
        Pool.ModifyLiquidityParams({
            tickLower: params.tickLower,
            tickUpper: params.tickUpper,
            liquidityDelta: params.liquidityDelta.toInt128(),
            tickSpacing: key.tickSpacing,
            salt: params.salt
        })
    );
}
```
Internal pre-conditions
External pre-conditions
Attack Path
Users will lose all funds deposited as liquidity in the collection initialization process. That is a minimum loss of 10 NFTs plus whatever WETH was provided for the other side of the liquidity pool. This leaves zero incentive for anyone to initialize a collection on the protocol.

## Proof of Concept

Proof of Concept is difficult for this one because the issue is about missing functionality, not broken functionality. However, the following code demonstrates a user initializing a collection and thereby funding a liquidity pool. Given that no function exists to allow the user to withdraw via the implementation contract, I've used PoolModifyLiquidityTest to provide the functionality, showing that it does not work for the original depositor (because it was deposited with a different peripheral contract) but does work for someone who deposits and withdraws via the same contract.
Please copy and paste import {PoolModifyLiquidityTest} from '@uniswap/v4-core/src/test/PoolModifyLiquidityTest.sol'; to the top of Locker.t.sol, and the following test into the body of the file:
```solidity
function test_InitializerLosesLiquidityProvided() public {
    address depositoor = makeAddr("depositoor");
    vm.startPrank(depositoor);
    ERC721Mock astroidDogs = new ERC721Mock();
    // Approve some of the ERC721Mock collections in our {Listings}
    locker.createCollection(address(astroidDogs), 'Astroid Dogs', 'ADOG', 0);
    address adog = address(locker.collectionToken(address(astroidDogs)));
    // mint the depositor enough dogs and eth, approve locker to spend
    uint[] memory tokenIds = new uint[](10);
    for (uint i = 0; i < 10; ++i) {
        astroidDogs.mint(depositoor, i);
        tokenIds[i] = i;
        astroidDogs.approve(address(locker), i);
    }
    deal(address(WETH), depositoor, 10e18);
    WETH.approve(address(locker), 10e18);
    // initialize collection
    locker.initializeCollection(address(astroidDogs), 10e18, tokenIds, 1, 79228162514264337593543950336);
    // there is no method to withdraw via locker or implementation
    // does a peripheral contract let us do this?
    // using poolModifyPosition as a helper
    // peripheral contract to allow deposits and withdrawals
    PoolModifyLiquidityTest poolModifyPosition = new PoolModifyLiquidityTest(poolManager);
    PoolKey memory key = abi.decode(uniswapImplementation.getCollectionPoolKey(address(astroidDogs)), (PoolKey));
    IPoolManager.ModifyLiquidityParams memory params = IPoolManager.ModifyLiquidityParams({
        tickLower: TickMath.minUsableTick(key.tickSpacing),
        tickUpper: TickMath.maxUsableTick(key.tickSpacing),
        liquidityDelta: -100,
        salt: ""
    });
    // the user who initiated it is unable to withdraw it with a different peripheral contract
    // that's because the Implementation contract owns the liquidity
    vm.expectRevert();
    poolModifyPosition.modifyLiquidity(key, params, "");
    // however, this peripheral contract would work for another user who deposits with it
    address secondDepositor = makeAddr("second");
    vm.startPrank(secondDepositor);
    // deal and approve funds
    deal(adog, secondDepositor, 1e18);
    deal(address(WETH), secondDepositor, 1e18);
    locker.collectionToken(address(astroidDogs)).approve(address(poolModifyPosition), 10e18);
    WETH.approve(address(poolModifyPosition), 10e18);
    // deposit and withdraw - no problem for this user
    IPoolManager.ModifyLiquidityParams memory depositParams = IPoolManager.ModifyLiquidityParams({
        tickLower: TickMath.minUsableTick(key.tickSpacing),
        tickUpper: TickMath.maxUsableTick(key.tickSpacing),
        liquidityDelta: 1e18,
        salt: ""
    });
    poolModifyPosition.modifyLiquidity(key, depositParams, "");
    IPoolManager.ModifyLiquidityParams memory withdrawParams = IPoolManager.ModifyLiquidityParams({
        tickLower: TickMath.minUsableTick(key.tickSpacing),
        tickUpper: TickMath.maxUsableTick(key.tickSpacing),
        liquidityDelta: -1e18,
        salt: ""
    });
    poolModifyPosition.modifyLiquidity(key, withdrawParams, "");
}
```

## Recommendation

Consider the following changes to UniswapImplementation.sol -
1. Store the user who initializes a collection in a mapping
2. Change _unlockCallback() such that it doesn't cast liquidityDelta to a uint (must allow negative values for withdrawals)
3. Add a remove liquidity function to Implementation.sol. It should check that only the initializer of a contract can call it and should call unlock() on the PoolManager, passing in the appropriate calldata to remove liquidity. It should then transfer funds received to the user.
These changes will allow a user to access the liquidity he or she initially provided.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a missing withdrawal path for the liquidity that is supplied when a new collection is initialized through the Uniswap v4 peripheral contract. During initialization the implementation contract calls unlock() on the PoolManager and immediately invokes modifyLiquidity with a positive liquidityDelta, which credits the newly added tokens to the implementation contract itself. Because the contract never calls unlock() again and the modifyLiquidity function is only reachable through the unlock callback, there is no subsequent call that can pass a negative liquidityDelta to remove the position. Consequently the implementation contract permanently owns the deposited assets and provides no function for the original depositor to retrieve them. An attacker does not need to perform any special action; any user who follows the normal workflow of calling locker.initializeCollection will have their WETH and NFTs locked in the pool with no way to withdraw, resulting in a total loss of the initial liquidity (for example ten NFTs and the corresponding WETH). The issue manifests whenever a collection is created, regardless of the amounts supplied, and affects every participant who attempts to bootstrap a pool on the protocol. It was discovered during a manual audit of the UniswapImplementation.sol source where the only unlockCallback was found to handle only the initialization case and the contract lacked any withdrawLiquidity method. The problem is subtle because the contract successfully creates the pool and the transaction does not revert, giving the impression that the operation succeeded, while the missing withdrawal logic is hidden. This class of bug can be described as an “irreversible liquidity lock” or “missing exit path” in decentralized exchange integrations. To remediate, the implementation should record the initializer’s address, allow modifyLiquidity to accept negative deltas via an unlock call, and expose a withdrawLiquidity function that validates the caller and transfers the retrieved tokens back to the user. From a user’s perspective the UI would show a successful collection creation, but later the user would see that their balance of NFTs and WETH remains unchanged or becomes zero, and attempts to claim a refund return nothing.
