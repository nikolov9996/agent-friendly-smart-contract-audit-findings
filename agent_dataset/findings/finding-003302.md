---
id: 3302
severity: "High"
---

# Flash loan not working due to transferFrom Issue

## Description

The issue arises when users attempt to use the flashLoanSimple function:
```solidity
function flashLoanSimple(
    IFlashLoanReceiver receiver,
    uint256 amount,
    bytes calldata params
) external nonReentrant {
    uint256 available = availableBorrowable();
    if (amount > available || amount > maxLoan) revert AmountTooHigh(amount);
    uint256 fee = exemptionList[msg.sender] ? 0 : amount.bp(fees.flash);
    uint256 toRepay = amount + fee;
    uint256 balanceBefore = asset.balanceOf(address(this));
    totalLent += amount;
    asset.safeTransferFrom(address(this), address(receiver), amount);
    receiver.executeOperation(address(asset), amount, fee, msg.sender, params);
    if ((asset.balanceOf(address(this)) - balanceBefore) < toRepay)
        revert FlashLoanDefault(msg.sender, amount);
    emit FlashLoan(msg.sender, amount, fee);
}
```
To transfer the fund to users, it uses asset.safeTransferFrom(address(this), address(receiver), amount); This line intends to transfer funds to the user. However, it fails because safeTransferFrom requires the contract to have a sufficient allowance to "spend" on behalf of itself. In the context of ERC20 tokens like USDC, the transferFrom function includes a crucial check: value <= allowed[from][msg.sender]. However, because the contract has not yet approved itself, leading to a situation where the allowance remains at zero, and hence the transferFrom call reverts.
```solidity
function transferFrom(
    address from,
    address to,
    uint256 value
) external override whenNotPaused notBlacklisted(msg.sender) notBlacklisted(from) notBlacklisted(to) returns (bool) {
    require(
        value <= allowed[from][msg.sender],
        "ERC20: transfer amount exceeds allowance"
    );
    _transfer(from, to, value);
    allowed[from][msg.sender] = allowed[from][msg.sender].sub(value);
    return true;
}
```
USDC - FiatTokenV1.sol: https://arbiscan.io/address/0xaf88d065e77c8cc2239327c5edb3a432268e5831 Using transfer does not require additional approval.

## Proof of Concept

No poc.

## Recommendation

Replacing the safeTransferFrom function with safeTransfer:
```solidity
function flashLoanSimple(
    IFlashLoanReceiver receiver,
    uint256 amount,
    bytes calldata params
) external nonReentrant {
    uint256 available = availableBorrowable();
    if (amount > available || amount > maxLoan) revert AmountTooHigh(amount);
    uint256 fee = exemptionList[msg.sender] ? 0 : amount.bp(fees.flash);
    uint256 toRepay = amount + fee;
    uint256 balanceBefore = asset.balanceOf(address(this));
    totalLent += amount;
    asset.safeTransfer(address(receiver), amount);
    receiver.executeOperation(address(asset), amount, fee, msg.sender, params);
    if ((asset.balanceOf(address(this)) - balanceBefore) < toRepay)
        revert FlashLoanDefault(msg.sender, amount);
    emit FlashLoan(msg.sender, amount, fee);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a misuse of the ERC20 transferFrom mechanism inside the flashLoanSimple function. The contract attempts to send the borrowed amount to the receiver by calling asset.safeTransferFrom(address(this), address(receiver), amount). For tokens that follow the standard ERC20 implementation, such as USDC, safeTransferFrom ultimately invokes transferFrom, which checks that the caller has an allowance from the source address (the contract itself) to move the specified amount. Because the contract never grants itself an allowance, the allowance mapping remains zero and the transferFrom call reverts with the message "ERC20: transfer amount exceeds allowance". This logical error prevents the flash loan from being issued, causing the entire flash loan transaction to fail before any funds are transferred. The impact is that borrowers cannot obtain flash loans, the protocol’s advertised functionality is broken, and users experience a mismatch between expectation (receiving a loan) and reality (receiving no funds and a revert). The issue manifests whenever the flash loan is requested with an ERC20 token that enforces allowance checks, such as USDC, and the contract has not pre‑approved itself. It affects any user or contract that tries to use the flash loan feature, as well as the protocol’s liquidity providers who rely on the flash loan revenue model. The problem was discovered during a manual code audit that highlighted the use of safeTransferFrom in a context where a simple transfer is required. The bug is subtle because the code compiles and the function signatures match, but the runtime allowance check is only triggered when the call is executed, making it easy to miss during testing if the specific token is not exercised. Conceptually, this is a class of allowance‑related token transfer bug where an internal contract attempts to move its own tokens using transferFrom without first setting an allowance, violating the ERC20 accounting assumptions. From a user’s perspective the UI may show a flash loan request that instantly fails, often with a generic error or no visible message, leaving the user confused as to why no funds were received. The correct remediation is to replace the safeTransferFrom call with safeTransfer, which does not require an allowance, or alternatively to set an explicit allowance for the contract to spend its own tokens before invoking transferFrom. Either approach restores the intended flow: the contract transfers the loan amount to the receiver, the receiver executes its operation, and the contract verifies repayment before emitting the FlashLoan event.
