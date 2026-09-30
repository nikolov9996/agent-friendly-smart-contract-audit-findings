---
id: 23018
severity: "High"
---

# Repaying a Loan with Permit in UErc20.sol Wrongly

## Description

The function _repayBorrowFresh in UErc20.sol wrongly calculates the interest to be paid when repaying a loan with a permit. The issue arises because the amount to repay is scaled to 1e18, but the interest is not, leading to users passing incorrect interest amounts based on the token's decimal places. This can result in users paying significantly less interest than they should for tokens with fewer decimal places (e.g., USDC, USDT) or more than they should for tokens with more decimal places.
The core of the problem lies in the different scaling applied to the amount and interest during the repayment process. In UErc20.sol, the function _repayBorrowFresh is called with the amount scaled to 1e18 but the interest remains unscaled, which causes incorrect interest calculations.
```solidity
function repayBorrowWithERC20Permit(
    address borrower,
    uint256 amount,
    uint256 deadline,
    uint8 v,
    bytes32 r,
    bytes32 s
) external whenNotPaused {
    IERC20Permit erc20Token = IERC20Permit(underlying);
    erc20Token.permit(msg.sender, address(this), amount, deadline, v, r, s);
    if (!accrueInterest()) revert AccrueInterestFailed();
    uint256 interest = calculatingInterest(borrower);

    _repayBorrowFresh(msg.sender, borrower, decimalScaling(amount, underlyingDecimal), interest);

}
```
Example
For tokens like USDC or USDT (which have 6 decimal places):
• If the interest to be paid is $2,000,000, the expected interest should be scaled to 1e18, resulting in $2,000,000 * 1e18.
• However, since the interest is not scaled, it remains at $2,000,000 * 1e6, leading to the contract recording less interest than should, the excess amount remains in the pool and it is not shared accordingly.
on-v2-contracts/contracts/market/UToken.sol#L568-L570 we use the above instead of using on-v2-contracts/contracts/market/UToken.sol#L682
For less amount of interest used in calculation this funds are stuck in the contract since it is not assigned to anyone to claim.
on-v2-contracts/contracts/market/UToken.sol#L705-L710
For tokens with more than 18 decimal places, the user would end up paying more interest than they should to the protocol and less funds will be available for all the lenders to claim their funds, resulting in overpayment.
This discrepancy creates an opportunity for the Wrong sharing of interest shares by protocol.
The impact of this vulnerability includes:
• Users potentially paying incorrect interest amounts, leading to financial losses for the protocol.
• Reduced profits for the protocol as interest calculations are not performed correctly.
Here is the problematic code snippet from UErc20.sol:
```solidity
uint256 interest = calculatingInterest(borrower);
_repayBorrowFresh(msg.sender, borrower, decimalScaling(amount, underlyingDecimal), interest);

```
In UDai.sol, although it is less critical because DAI has 18 decimals, the same logic flaw exists.
Below is the Reference to the code if the user pays normally on-v2-contracts/contracts/market/UToken.sol#L679-L684
Interest is scaled there properly and sent to the _repayBorrowFresh and use the permit because if the incorrect implementation.

## Proof of Concept

no poc

## Recommendation

To address this issue, the interest should be scaled correctly according to the token's decimal places. The function call should ensure both the amount and the interest are appropriately scaled. Here's the recommended fix:
```solidity
function repayBorrowWithPermit(uint256 amount, ...) external {
    ,!
    -- uint256 interest = calculatingInterest(borrower);
    ++ uint256 interest = _calculatingInterest(borrower);
    _repayBorrowFresh(msg.sender, borrower, decimalScaling(amount, underlyingDecimal), Interest);

}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mismatched decimal scaling bug in the loan‑repayment path that uses ERC20 permits. When a borrower calls the function that permits a token transfer and then repays a loan, the contract scales the principal amount to the internal 1e18 representation but leaves the accrued interest in the token’s native decimal format. Because the interest value is not multiplied by the same scaling factor, the protocol records an interest amount that is too small for tokens with fewer than 18 decimals (for example USDC or USDT with 6 decimals) and too large for tokens with more than 18 decimals. The root cause is the call to _repayBorrowFresh with decimalScaling(amount, underlyingDecimal) for the amount while passing the raw interest returned by calculatingInterest(borrower). An attacker or honest user can exploit this by repaying a loan with a low‑decimal token and receiving a refund of interest that should have been paid to lenders, or by overpaying interest with a high‑decimal token, thereby reducing the pool of funds available to other lenders. The impact includes users paying an incorrect interest amount, excess interest becoming trapped in the contract without an owner, and the protocol’s profit and interest‑sharing calculations becoming inaccurate. The condition occurs whenever the repayBorrowWithERC20Permit function is used, i.e., when a borrower supplies a permit signature and the contract attempts to accrue interest before repayment. All borrowers, lenders and the protocol itself are affected because the accounting invariants that guarantee that total interest earned equals interest distributed are broken. The issue was discovered during a formal security audit (Sherlock) that compared the implementation against the reference UToken contract where interest is correctly scaled. The bug is subtle because the function signatures appear correct and the permit flow works; only the hidden scaling mismatch causes the accounting error, which may not be visible until a repayment is performed and the pool balances are examined. To fix the problem, the interest value must be scaled using the same decimal factor as the principal before being passed to _repayBorrowFresh, ensuring that both amount and interest are expressed in the same 1e18 internal unit. This aligns the repayment logic with the reference implementation and restores correct interest distribution and pool balance consistency.
