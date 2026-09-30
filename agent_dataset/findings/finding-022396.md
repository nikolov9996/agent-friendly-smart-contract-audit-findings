---
id: 22396
severity: "High"
---

# Lender transactions can be front-run, leading

## Description

Users can mint wfCash tokens via mintViaUnderlying by passing a variable minImpliedRate to guard against trade slippage. If the market interest is lower than expected by the user, the transaction will revert due to slippage protection.
However, if the user mints a share larger than maxFCash, the minImpliedRate check is not performed.
023-12-notional-update-5/blob/3bf2fb5d992dfd5aa7343d7788e881d3a4294b13/wrapped-fcash/contracts/wfCashLogic.sol#L25-L33
```solidity
function mintViaUnderlying(
    uint256 depositAmountExternal,
    uint88 fCashAmount,
    address receiver,
    uint32 minImpliedRate // Added to protect against slippage.
) external override {
    (/* */, uint256 maxFCash) = getTotalFCashAvailable();
    _mintInternal(depositAmountExternal, fCashAmount, receiver, minImpliedRate, maxFCash);
}
```
let's dive into _mintInternal we can see if maxFCash < fCashAmount, the value of
-update-5/blob/3bf2fb5d992dfd5aa7343d7788e881d3a4294b13/wrapped-fcash/contracts/wfCashLogic.sol#L60-L68
```solidity
if (maxFCash < fCashAmount) {
    uint256 fCashAmountExternal = fCashAmount * precision / (underlyingTokenDecimals) / 1e8;
    require(fCashAmountExternal <= depositAmountExternal);
    // This means the amount was transferred back to the account
    NotionalV2.depositUnderlyingToken{value: msgValue}(address(this),
}
```
Imagine the following scenario:
• lender deposit Underlying token to mint some shares and set a minImpliedRate to protect the transaction
• alice front-run her transaction invoke mint to mint some share
• the shares of lender mint now is bigger than maxFCash
• now the lender lending at zero
```solidity
function testDepositViaUnderlying() public {
    address alice = makeAddr("alice");
    deal(address(asset), LENDER, 8800 * precision, true);
    deal(address(asset), alice, 5000 * precision, true);
    //alice deal.
    vm.stopPrank();
    vm.startPrank(alice);
    asset.approve(address(w), type(uint256).max);
    //==============================LENDER START=============================//
    vm.stopPrank();
    vm.startPrank(LENDER);
    asset.approve(address(w), type(uint256).max);
    //user DAI balance before:
    assertEq(asset.balanceOf(LENDER), 8800e18);
    (/* */, uint256 maxFCash) = w.getTotalFCashAvailable();
    console2.log("current maxFCash:",maxFCash);
    //LENDER mintViaUnderlying will revert due to slippage.
    uint32 minImpliedRate = 0.15e9;
    vm.expectRevert("Trade failed, slippage");
    w.mintViaUnderlying(5000e18,5000e8,LENDER,minImpliedRate);
    //==============================LENDER END=============================//
    //======================alice frontrun to mint some shares.============//
    vm.stopPrank();
    vm.startPrank(alice);
    w.mint(5000e8,alice);
    //==========================LENDER TX =================================//
    vm.stopPrank();
    vm.startPrank(LENDER);
    asset.approve(address(w), type(uint256).max);
    //user DAI balance before:
    assertEq(asset.balanceOf(LENDER), 8800e18);
    //LENDER mintViaUnderlying will success.
    w.mintViaUnderlying(5000e18,5000e8,LENDER,minImpliedRate);
    console2.log("lender mint token:",w.balanceOf(LENDER));
    console2.log("lender cost DAI:",8800e18 - asset.balanceOf(LENDER));
}
```
From the above test, we can observe that if maxFCasha is greater than 5000e8, the lender's transaction will be reverted due to "Trade failed, slippage." Subsequently, if Alice front-runs by invoking mint to create some shares before the lender, the lender's transaction will succeed. Therefore, the lender's minImpliedRate check will be bypassed, leading to a loss of funds for the lender.
lender lost of funds
fd5aa7343d7788e881d3a4294b13/wrapped-fcash/contracts/wfCashLogic.sol#L60-L68
```solidity
if (maxFCash < fCashAmount) {
    uint256 fCashAmountExternal = fCashAmount * precision / (underlyingTokenDecimals) / 1e8;
    require(fCashAmountExternal <= depositAmountExternal);
    // This means the amount was transferred back to the account
    NotionalV2.depositUnderlyingToken{value: msgValue}(address(this),
}
```

## Proof of Concept

no poc

## Recommendation

add a check inside _mintInternal
```solidity
if (maxFCash < fCashAmount) {
    require(minImpliedRate == 0, "Trade failed, slippage");
    uint256 fCashAmountExternal = fCashAmount * precision / (underlyingTokenDecimals) / 1e8;
    require(fCashAmountExternal <= depositAmountExternal);
    // This means the amount was transferred back to the account
    NotionalV2.depositUnderlyingToken{value: msgValue}(address(this),
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract provides a function that lets a user deposit an underlying token and receive wrapped fCash (wfCash) tokens in return. The caller can supply a parameter called minImpliedRate which is intended to protect the transaction from excessive slippage: if the market rate falls below the supplied threshold the call should revert. The implementation performs this check in the normal execution path, but when the requested fCash amount exceeds the currently available liquidity (maxFCash) the internal routine _mintInternal takes a different branch. In that branch the code only verifies that the underlying amount is sufficient and then proceeds to deposit the underlying token without ever consulting the minImpliedRate value. As a result, a malicious actor can front‑run a legitimate lender by minting a small amount of wfCash just before the lender’s transaction. The front‑run reduces maxFCash so that the lender’s request now falls into the bypassed branch. The lender’s slippage protection is silently ignored, the transaction succeeds, and the lender ends up paying the full underlying amount while receiving wfCash at an effectively zero implied rate. From the user’s perspective the transaction that was expected to revert due to slippage instead succeeds, the underlying token balance drops more than anticipated, and the received wfCash tokens are worth far less than expected – effectively a loss of funds. The vulnerability is a classic missing‑validation or logic‑bypass bug that can be exploited through front‑running. It was discovered during a manual audit when the auditor constructed a unit test that simulated the front‑run scenario and observed the unexpected success of the lender’s transaction. The issue is hard to notice because the normal code path correctly enforces the slippage check; only the edge case where maxFCash < fCashAmount is affected, and that path is rarely exercised in standard testing. The fix is to ensure that the minImpliedRate condition is evaluated regardless of the liquidity branch, for example by adding an explicit require that rejects the transaction when minImpliedRate is non‑zero and maxFCash is insufficient, or by moving the slippage validation before the branch that handles the low‑liquidity case. By restoring the invariant that every mint operation must respect the caller‑provided slippage guard, the protocol regains its intended accounting guarantees and prevents attackers from extracting value by front‑running.
