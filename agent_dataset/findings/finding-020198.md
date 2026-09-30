---
id: 20198
severity: "High"
---

# Lack of segregation between users' assets and

## Description

The users' assets are wrongly sent to the owner due to a lack of segregation between users' assets and collected fees, which might result in an irreversible loss of assets for the victims.
GLX uses the Chainlink Automation to execute the LimitOrderRegistry.performUpkeep function when there are orders that need to be fulfilled. The LimitOrderRegistry contract must be funded with LINK tokens to keep the operation running.
To ensure the LINK tokens are continuously replenished and funded, users must pay a fee denominated in Native ETH or ERC20 WETH tokens on orders claiming as shown below. The collected ETH fee will be stored within the LimitOrderRegistry contract.
/src/LimitOrderRegistry.sol#L696
File: LimitOrderRegistry.sol
```solidity
function claimOrder(uint128 batchId, address user) external payable returns (ERC20, uint256) {
    // ..SNIP..
    // Transfer tokens owed to user.
    tokenOut.safeTransfer(user, owed);
    // Transfer fee in.
    address sender = _msgSender();
    if (msg.value >= userClaim.feePerUser) {
        // refund if necessary.
        uint256 refund = msg.value - userClaim.feePerUser;
        if (refund > 0) sender.safeTransferETH(refund);
    } else {
        WRAPPED_NATIVE.safeTransferFrom(sender, address(this), userClaim.feePerUser);
        // If value is non zero send it back to caller.
        if (msg.value > 0) sender.safeTransferETH(msg.value);
    }
    // ..SNIP..
```
To retrieve the ETH fee collected, the owner will call the LimitOrderRegistry.withdrawNative function that will send all the Native ETH and ERC20 WETH tokens within the LimitOrderRegistry contract to the owner's address. After executing this function, the Native ETH and ERC20 WETH tokens on this contract will be zero and wiped out.
/src/LimitOrderRegistry.sol#L505
File: LimitOrderRegistry.sol
```solidity
function withdrawNative() external onlyOwner {
    uint256 wrappedNativeBalance = WRAPPED_NATIVE.balanceOf(address(this));
    uint256 nativeBalance = address(this).balance;
    // Make sure there is something to withdraw.
    if (wrappedNativeBalance == 0 && nativeBalance == 0) revert LimitOrderRegistry__ZeroNativeBalance();
    // transfer wrappedNativeBalance if it exists
    if (wrappedNativeBalance > 0) WRAPPED_NATIVE.safeTransfer(owner, wrappedNativeBalance);
    // transfer nativeBalance if it exists
    if (nativeBalance > 0) owner.safeTransferETH(nativeBalance);
}
```
Most owners will automate replenishing the LimitOrderRegistry contract with LINK tokens to ensure its balance does not fall below zero and for ease of maintenance. For instance, a certain percentage of the collected ETH fee (e.g., 50%) will be swapped immediately to LINK tokens on a DEX upon collection and transferred the swapped LINK tokens back to the LimitOrderRegistry contract. The remaining will be spent to cover operation and maintenance costs.
However, the issue is that there are many Uniswap V3 pools where their token pair consists of ETH/WETH. In fact, most large pools in Uniswap V3 will consist of ETH/WETH. For instance, the following Uniswap pools consist of ETH/WETH as one of the pool tokens:
• Assume that the owner has configured and setup the LimitOrderRegistry contract to work with the Uniswap DAI/ETH pool, and the current price of the DAI/ETH pool is 1,500 DAI/ETH.
Bob submit a new Buy Limit Order swapping DAI to ETH at the price of 1,000 DAI/ETH. Bob would deposit 1,000,000 DAI to the LimitOrderRegistry contract.
When Bob's Buy Limit Order is ITM and fulfilled, 1000 ETH/WETH will be sent to and stored within the LimitOrderRegistry contract.
The next step that Bob must do to claim the swapped 1000 ETH/WETH is to call the LimitOrderRegistry.claimOrder function, which will collect the fee and transfer the swapped 1000 ETH/WETH to Bob.
Unfortunately, before Bob could claim his swapped ETH/WETH, the LimitOrderRegistry.withdrawNative function is triggered by the owner or the function is triggered, all the Native ETH and ERC20 WETH tokens on this contract will be transferred to the owner's address. As a result, Bob's 1000 swapped ETH/WETH stored within the LimitOrderRegistry contract are sent to the owner's address, and the balance of ETH/WETH in the LimitOrderRegistry contract is zero.
When Bob calls the LimitOrderRegistry.claimOrder function, the transaction will revert because insufficient ETH/WETH is left in the LimitOrderRegistry contract.
Unfortunately for Bob, there is no way to recover back his ETH/WETH that is sent to the owner's address. Following outline some of the possible scenarios where this could happen:
– The owners set up their infrastructure to automatically swap a portion or all the ETH/WETH received to LINK tokens and transfer them to the LimitOrderRegistry contract, and there is no way to retrieve the deposited LINK tokens from the LimitOrderRegistry contract even if the owner wishes to do so as there is no function within the contract to allow this action.
– The owners set up their infrastructure to automatically swap a small portion of ETH/WETH received to LINK tokens and send the rest of the ETH/WETH to 100 investors/DAO members' addresses. So, it is no guarantee that the investors/DAO members will return the ETH/WETH to Bob.
Loss of assets for the users

## Proof of Concept

no poc

## Recommendation

Consider implementing one of the following solutions to mitigate the issue:
Solution 1 - Only accept Native ETH as fee
Uniswap V3 pool stored ETH as Wrapped ETH (WETH) ERC20 token internally. When the collect function is called against the pool, WETH ERC20 tokens are returned to the caller. Thus, the most straightforward way to mitigate this issue is to update the contract to collect the fee in Native ETH only.
In this case, there will be a clear segregation between users' assets (WETH) and owner's fee (Native ETH)
```solidity
function withdrawNative() external onlyOwner {
    uint256 nativeBalance = address(this).balance;
    // Make sure there is something to withdraw.
    if (nativeBalance == 0) revert LimitOrderRegistry__ZeroNativeBalance();
    // transfer nativeBalance if it exists
    if (nativeBalance > 0) owner.safeTransferETH(nativeBalance);
}
function claimOrder(uint128 batchId, address user) external payable returns (ERC20, uint256) {
    // ..SNIP..
    // Transfer tokens owed to user.
    tokenOut.safeTransfer(user, owed);
    // Transfer fee in.
    address sender = _msgSender();
    if (msg.value >= userClaim.feePerUser) {
        // refund if necessary.
        uint256 refund = msg.value - userClaim.feePerUser;
        if (refund > 0) sender.safeTransferETH(refund);
    } else {
        revert LimitOrderRegistry__InsufficientFee;
    }
    // ..SNIP..
```
Solution 2 - Define state variables to keep track of the collected fee
Consider defining state variables to keep track of the collected fee so that the fee will not mix up with users' assets.
```solidity
function claimOrder(uint128 batchId, address user) external payable returns (ERC20, uint256) {
    // ..SNIP..
    // Transfer fee in.
    address sender = _msgSender();
    if (msg.value >= userClaim.feePerUser) {
        collectedNativeETHFee += userClaim.feePerUser;
        // refund if necessary.
        uint256 refund = msg.value - userClaim.feePerUser;
        if (refund > 0) sender.safeTransferETH(refund);
    } else {
        collectedWETHFee += userClaim.feePerUser;
        WRAPPED_NATIVE.safeTransferFrom(sender, address(this), userClaim.feePerUser);
        // If value is non zero send it back to caller.
        if (msg.value > 0) sender.safeTransferETH(msg.value);
    }
    // ..SNIP..
}
function withdrawNative() external onlyOwner {
    uint256 wrappedNativeBalance = collectedWETHFee;
    uint256 nativeBalance = collectedNativeETHFee;
    collectedWETHFee = 0; // clear the fee
    collectedNativeETHFee = 0; // clear the fee
    // Make sure there is something to withdraw.
    if (wrappedNativeBalance == 0 && nativeBalance == 0) revert LimitOrderRegistry__ZeroNativeBalance();
    // transfer wrappedNativeBalance if it exists
    if (wrappedNativeBalance > 0) WRAPPED_NATIVE.safeTransfer(owner, wrappedNativeBalance);
    // transfer nativeBalance if it exists
    if (nativeBalance > 0) owner.safeTransferETH(nativeBalance);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mixing of users' swapped assets with the protocol fee pool, which allows the contract owner to withdraw both the fee and the users' tokens in a single operation. The root cause is that the LimitOrderRegistry contract stores native ETH and wrapped ETH (WETH) received as fee together with the ETH/WETH that belong to users after a limit order is fulfilled, without any accounting separation. Because the withdrawNative function transfers the entire native ETH balance and the entire WETH balance to the owner, an owner who calls this function before a user invokes claimOrder can empty the contract of the user’s swapped tokens. An attacker (or the owner) can simply trigger withdrawNative at any time, causing the user’s assets to be sent to the owner’s address. The impact is that users who have placed limit orders lose the tokens they expected to receive; when they later call claimOrder the transaction reverts due to insufficient balance, and the lost assets cannot be recovered. This situation occurs whenever the fee is collected in ETH or WETH and the contract does not keep a separate ledger for fees, which is typical in setups that automatically swap a portion of collected ETH/WETH to LINK for upkeep. The affected parties are the users who submit limit orders, any investors relying on the protocol, and the protocol itself because the loss of user funds undermines trust. The issue was discovered during a security audit that examined the flow of fee collection and withdrawal. It is hard to notice because the withdrawNative function appears legitimate and the contract’s balance checks do not differentiate between fee and user assets. To remediate, the contract should segregate fee and user assets, for example by accepting only native ETH as fee and keeping it separate from user‑owned WETH, or by introducing dedicated state variables that track collected fees and are the only amounts withdrawn by the owner. This prevents the owner from inadvertently or maliciously draining user funds and restores the expected accounting invariant that user assets remain untouched until the user successfully claims them.
