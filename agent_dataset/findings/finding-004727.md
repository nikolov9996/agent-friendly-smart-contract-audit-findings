---
id: 4727
severity: "High"
---

# The swapexactinputsinglehop function in the llido library consistently fails Submitted by merlin, also found by 0xrex, zigtur, deth, hals, Rotciv Egaf, 0xRizwan, Spearmint, ast3ros, smbv19192323, 0xblackskull, Said and 0xluckyy

## Description

The functions LLido.allToWsteth, LLido.sellWsteth(), and LLido.allToEth() are utilized in various parts of the Controller smart contract during the execution of ethStake, earningPulls, lockWithdraw, earningWithdraw, and other functions. These functions, in turn, invoke swapExactInputSingleHop():
```solidity
library LLido
function swapExactInputSingleHop(
    address tokenIn,
    address tokenOut,
    uint amountIn
)
internal
returns (uint amountOut) {
    ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
    .ExactInputSingleParams({
        tokenIn: tokenIn,
        tokenOut: tokenOut,
        fee: POOL_FEE,
        recipient: address(this),
        // deadline: block.timestamp,
        amountIn: amountIn,
        amountOutMinimum: 0,
        sqrtPriceLimitX96: 0
    });
    amountOut = router.exactInputSingle(params);
}
```
The value of deadline is commented out, but the router, where the exactInputSingle function is called, checks this value:
```solidity
modifier checkDeadline(uint256 deadline) {
    require(_blockTimestamp() <= deadline, 'Transaction too old');
    _;
}
```
As a result, the protocol will not function properly, and essential functions will fail with the reason Transaction too old.

## Proof of Concept

no poc

## Recommendation

Consider passing the deadline value for the successful execution of the function:
```solidity
function swapExactInputSingleHop(
    address tokenIn,
    address tokenOut,
    uint amountIn,
    uint deadline_
)
internal
returns (uint amountOut) {
    ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
    .ExactInputSingleParams({
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from a missing deadline parameter in the LLido library function swapExactInputSingleHop, which builds an ISwapRouter.ExactInputSingleParams struct without supplying a value for the deadline field. In Uniswap V3's router, the exactInputSingle function is guarded by a checkDeadline modifier that requires the current block timestamp to be less than or equal to the supplied deadline; if the deadline is zero (the default value when omitted), the condition fails and the transaction reverts with the generic error message "Transaction too old". This logical omission propagates to every higher‑level controller function that relies on the swap, such as ethStake, earningPulls, lockWithdraw, and earningWithdraw. When a user initiates a stake or withdrawal, the contract attempts to perform the token swap, the router rejects the call, and the whole operation aborts. From the user’s perspective the UI may show that a stake or withdrawal was submitted but the balance remains unchanged, or that a refund amount is zero, leading to confusion and the impression that the protocol is broken or possibly malicious. The issue was discovered during a manual audit of the controller’s flow, where the auditor noticed that the deadline line in the params struct was commented out and that calls consistently reverted with the deadline error. Because the revert message does not reference the missing field directly, the problem can be hard to spot; developers may attribute the failure to network congestion or gas limits instead of a contract‑level logic error. The impact is a denial‑of‑service condition: no user can successfully execute staking, withdrawing, or any operation that depends on the swap, effectively freezing funds that are already in the contract. No funds are transferred out of the contract, so there is no direct theft vector, but the protocol’s core functionality is unusable until the bug is fixed. The appropriate remediation is to pass a realistic deadline value—typically block.timestamp plus a reasonable buffer—when constructing the ExactInputSingleParams, or to redesign the library to accept a deadline argument from callers. This class of bug falls under missing‑parameter validation or deadline misconfiguration, where a required time‑bound check is bypassed, causing systematic transaction failures and breaking business logic that assumes successful token swaps.
