---
id: 4191
severity: "Critical"
---

# The granularity of 1M tokens for buy and sell operations in the BondingCurve contract leads to user fund losses

## Description

The current implementation contains significant flaws that disrupt the system and cause substantial losses for users. These issues arise because the calculations for buy and sell amounts are truncated to full millions of tokens.
In the buy() function, when a user transfers ETH to buy tokens, if the resulting amount of tokens for a given trade is, for example, 1.9M tokens, the user will still pay as if he is receiving 1.9M tokens but will only receive 1M. This results in a loss of approximately 47%.
```solidity
uint256 actualTokens = (tokensToTransfer / 1e18) * 1_000_000 * 1e18;
```
In the sell() function, if a user transfers 1.9M tokens to sell, he will only be refunded ETH equivalent to 1M tokens, but the entire 1.9M tokens will be transferred to the contract. This results in a similar 47% loss. Furthermore, incorrect deduction of the internal n virtual accounting value, used for bonding curve calculations, leads to inaccurate stored values, which inflates the token price.
```solidity
uint256 newN = n - (tokenAmount / (1_000_000)); // <-- truncation
uint256 currentETH = ethForN(n);
uint256 newETH = ethForN(newN);
uint256 refundETH = currentETH - newETH;

require(
    tokenContract.transferFrom(msg.sender, address(this), tokenAmount),
    "Token transfer failed"
);
```
```solidity
function ethForN(uint256 n_) public pure returns (uint256) {
    uint256 n_value = n_ / 1e18; // <-- truncation
```
This issue stems from the ethForN() function, where the bonding curve is implemented as a step function that calculates values per million tokens. The decision to use cubic calculations in the bonding curve introduced complications, and to avoid overflows, the calculations were restricted to per-million token steps, which impacts both the linear and cubic parts of the equation.

## Proof of Concept

no poc

## Recommendation

While there is no simple solution for cubic calculations, the bonding curve can be updated to better align with expected calculations and business requirements. The curve can be smoothed by implementing a linear function with a granularity of 1 wei and a cubic part with a granularity of 1e6, instead of the current 1e24 granularity for both parts.
Update the ethForN() function as follows:
```solidity
function ethForN(uint256 n_) public pure returns (uint256) {
    uint256 linear = (P0 * n_) / 1e18;
    uint256 cubic = (A * ((n_ / 1e6) ** 3)) / 1e54;
    return linear + cubic;
}
```
Where P0 is 5e9 and A is 60e9.
In addition to updating ethForN(), make the following adjustments to ensure consistency with the updated bonding curve:
- In solveForN(), use uint256 high = MAX_MILLION_TOKENS * 1e24.
- Remove adjustments to millions in the buy() and sell() functions.
- Update the old require:
```solidity
require(newN <= MAX_MILLION_TOKENS * 1e18, "Max token supply reached");
```
and adjust it to correctly check for 500M tokens.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a rounding and granularity error in the bonding‑curve contract that treats token amounts in steps of one million. The buy() function calculates the number of tokens to transfer by dividing the raw token amount by 1e18, multiplying by 1_000_000 and then re‑applying 1e18, which truncates any fractional part of a million. As a result, when a user sends ETH that should purchase 1.9 million tokens, the contract charges for the full 1.9 million but only transfers 1 million, causing an immediate loss of roughly 47 percent of the expected tokens. The sell() function suffers the same problem in reverse: a user who transfers 1.9 million tokens receives ETH only for 1 million tokens, while the full 1.9 million are deducted from the user’s balance. In addition, the internal accounting variable n, which represents the virtual token supply used by the bonding‑curve pricing formula, is updated with a division by 1_000_000, truncating the same fractional part and inflating the stored price. The ethForN() helper also divides n by 1e18, creating a step‑function that only updates the price at whole‑million boundaries. The bug manifests whenever a trade amount is not an exact multiple of one million tokens, which is common for most users. From a user’s perspective the UI may show that the correct amount of ETH was sent or that the correct number of tokens was entered, but the resulting token balance is lower than expected or the refunded ETH is smaller, leading to “funds disappear” or “refund missing” symptoms. The issue was discovered during a manual audit that compared the mathematical model of the bonding curve with the on‑chain implementation and identified the truncation points. It is hard to notice because the contract does not revert; it simply returns a smaller amount, so no explicit error is emitted. The vulnerability belongs to the class of rounding/truncation bugs and step‑function mis‑implementation that break accounting invariants. To remediate, the contract should eliminate the per‑million granularity, perform calculations with full precision (e.g., using wei‑level linear terms and a cubic term with appropriate scaling), and update ethForN, solveForN, buy() and sell() to use exact arithmetic without integer division that discards remainders. This will align the on‑chain pricing with the intended bonding‑curve formula and prevent users from losing funds due to systematic under‑payment or under‑refund.
