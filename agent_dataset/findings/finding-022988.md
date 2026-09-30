---
id: 22988
severity: "High"
---

# Incorrect valuation of vault share

## Description

The code for computing the valuation of the vault shares was found to be incorrect. As a result, the account's collateral will be overinflated, allowing malicious users to borrow significantly more than the actual collateral value, draining assets from the protocol.
Let BT be the borrowed token with 6 decimal precision, and RT be the redemption token with 18 decimal precision. When a withdraw request has split and is finalized, the following _getValueOfSplitFinalizedWithdrawRequest function will be used to calculate the value of a withdraw request in terms of the borrowed token (BT).
In Line 77 below, the Deployments.TRADING_MODULE.getOraclePrice function will be called to fetch the exchange rate of the redemption token (RT) and borrowed token (BT).
-vaults-private/contracts/vaults/common/WithdrawRequestBase.sol#L77
File: WithdrawRequestBase.sol
```solidity
function _getValueOfSplitFinalizedWithdrawRequest(
    WithdrawRequest memory w,
    SplitWithdrawRequest memory s,
    address borrowToken,
    address redeemToken
) internal virtual view returns (uint256) {
    // If the borrow token and the withdraw token match, then there is no need to apply
    // an exchange rate at this point.
    if (borrowToken == redeemToken) {
        return (s.totalWithdraw * w.vaultShares) / s.totalVaultShares;
    } else {
        // Otherwise, apply the proper exchange rate
        (int256 rate, /* */) = Deployments.TRADING_MODULE.getOraclePrice(redeemToken, borrowToken);
        return (s.totalWithdraw * rate.toUint() * w.vaultShares) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION);
    }
}
```
Within the Deployments.TRADING_MODULE.getOraclePrice function, chainlink oracle Assume that one BT is worth 1 USD, so the quotePrice will be 1e8. Assume that oracle's price is always denominated in 8 decimals for USD price feed. This function will always return the exchange rate is RATE_DECIMALS (18 decimals - Hardcoded). Thus, based on the calculation in Lines 283-285, the exchange rate returned will be 10e18, which is equivalent to one unit of RT is worth 10 units of BT.
-vaults-private/contracts/trading/TradingModule.sol#L283
File: TradingModule.sol
```solidity
/// @notice Returns the Chainlink oracle price between the baseToken and the quoteToken, the
/// Chainlink oracles. The quote currency between the oracles must match or the conversion
/// in this method does not work. Most Chainlink oracles are baseToken/USD pairs.
/// @param baseToken address of the first token in the pair, i.e. USDC in USDC/DAI
/// @param quoteToken address of the second token in the pair, i.e. DAI in USDC/DAI
/// @return answer exchange rate in rate decimals
/// @return decimals number of decimals in the rate, currently hardcoded to 1e18
function getOraclePrice(address baseToken, address quoteToken)
public
view
override
returns (int256 answer, int256 decimals)
{
    _checkSequencer();
    PriceOracle memory baseOracle = priceOracles[baseToken];
    PriceOracle memory quoteOracle = priceOracles[quoteToken];
    int256 baseDecimals = int256(10**baseOracle.rateDecimals);
    int256 quoteDecimals = int256(10**quoteOracle.rateDecimals);
    (/* */, int256 basePrice, /* */, uint256 bpUpdatedAt, /* */) = baseOracle.oracle.latestRoundData();
    require(block.timestamp - bpUpdatedAt <= maxOracleFreshnessInSeconds);
    require(basePrice > 0); /// @dev: Chainlink Rate Error
    (/* */, int256 quotePrice, /* */, uint256 qpUpdatedAt, /* */) = quoteOracle.oracle.latestRoundData();
    require(block.timestamp - qpUpdatedAt <= maxOracleFreshnessInSeconds);
    require(quotePrice > 0); /// @dev: Chainlink Rate Error
    answer =
        (basePrice * quoteDecimals * RATE_DECIMALS) /
        (quotePrice * baseDecimals);
    decimals = RATE_DECIMALS;
}
```
following:
• s.totalWithdraw is the total RT claimed and is denominated in 18 decimals (Token's native precision). Assume that s.totalWithdraw=100e18 RT was claimed.
• w.vaultShares and s.totalVaultShares are the number of vault shares and is denominated in 8 decimals (INTERNAL_TOKEN_PRECISION). Assume that w.vaultShares=5e8 and s.totalVaultShares=10e8
• Constants.EXCHANGE_RATE_PRECISION is 1e18
Intuitively, the split's total withdraw (s.totalWithdraw) is 100 units of RT. In terms of the borrowed token (BT), it will be 1000 units of BT since the price is (1:10). Since the withdraw request owns 50% of the vault shares in the split withdraw request, it is entitled to 500 units of BT.
-vaults-private/contracts/vaults/common/WithdrawRequestBase.sol#L77
File: WithdrawRequestBase.sol
```solidity
function _getValueOfSplitFinalizedWithdrawRequest(
    WithdrawRequest memory w,
    SplitWithdrawRequest memory s,
    address borrowToken,
    address redeemToken
) internal virtual view returns (uint256) {
    // If the borrow token and the withdraw token match, then there is no need to apply
    // an exchange rate at this point.
    if (borrowToken == redeemToken) {
        return (s.totalWithdraw * w.vaultShares) / s.totalVaultShares;
    } else {
        // Otherwise, apply the proper exchange rate
        (int256 rate, /* */) = Deployments.TRADING_MODULE.getOraclePrice(redeemToken, borrowToken);
        return (s.totalWithdraw * rate.toUint() * w.vaultShares) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION);
    }
}
```
To calculate the value of a withdraw request in terms of the borrowed token (BT), the following formula at Line 79 above will be used:
(s.totalWithdraw * rate * w.vaultShares) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION)
(100e18 * 10e18 * 5e8) / (10e8 * 1e18)
500000000000000e6
However, the code above indicates that the withdraw request is entitled to 500000000000000 units of BT instead of 500 units of BT, which is overly inflated. As a result, the account's collateral will be overly inflated. The account's collateral will be overinflated, allowing malicious users to borrow significantly more than the actual collateral value, stealing assets from the protocol.

## Proof of Concept

no poc

## Recommendation

Update the formula to as follows:
```solidity
(s.totalWithdraw * rate.toUint() * w.vaultShares * BORROW_PRECISION) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION * REDEMPTION_PRECISION);
```
BORROW_PRECISION = 1e6 and REDEMPTION_PRECISION = 1e18.
Let's redo the calculation to verify that the new formula works as intended:
(s.totalWithdraw * rate.toUint() * w.vaultShares * BORROW_PRECISION) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION * REDEMPTION_PRECISION);
(100e18 * 10e18 * 5e8 * 1e6) / (10e8 * 1e18 * 1e18)
500e6
The new formula returned 500 units of BT, which is correct.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect valuation of vault shares that arises when the contract converts a withdrawal amount expressed in the redemption token (RT) to the borrowed token (BT) using an oracle price that is returned with 18‑decimal precision, but the conversion formula does not account for the differing token precisions. The root cause is a missing scaling factor for the borrowed token’s native precision (6 decimals) and the redemption token’s native precision (18 decimals) together with the constant EXCHANGE_RATE_PRECISION, which leads to a multiplication by 1e12 that inflates the computed value of a split‑finalized withdraw request. An attacker can exploit this by submitting a withdraw request that, after the flawed calculation, appears to be worth far more BT than the actual RT deposited. The contract then records an over‑inflated collateral amount for the attacker, allowing them to borrow significantly more BT than should be permitted. The impact is that the protocol’s accounting is broken: users may see their collateral reported as huge numbers, loans are granted against phantom value, and assets can be drained from the vault. The condition under which the bug manifests is any situation where borrowToken and redeemToken differ and the oracle price is fetched via Deployments.TRADING_MODULE.getOraclePrice, which always returns a rate with 18‑decimal precision. All participants who rely on the vault’s collateral – borrowers, lenders, and the protocol itself – are affected because the inflated collateral undermines the security model. The issue was discovered during a manual audit that examined the arithmetic in WithdrawRequestBase.sol and identified that the formula (s.totalWithdraw * rate * w.vaultShares) / (s.totalVaultShares * Constants.EXCHANGE_RATE_PRECISION) does not normalize the units of rate, totalWithdraw, and vaultShares, resulting in a value that is off by a factor of 1e12. The bug is hard to notice because the numbers involved are large and the contract uses high‑precision arithmetic throughout, masking the unit mismatch. To fix the problem, the conversion formula must be adjusted to include the borrowed token precision (BORROW_PRECISION = 1e6) and the redemption token precision (REDEMPTION_PRECISION = 1e18) in the denominator, effectively scaling the rate back to the correct unit basis. Conceptually, the fix restores proper unit handling so that the value of a withdraw request is computed in the same decimal space as the borrowed token, preventing collateral over‑inflation and preserving the protocol’s accounting invariants. This class of bug is a precision‑handling or units‑mismatch arithmetic error, often seen in cross‑token calculations where token decimals differ and oracle prices are expressed with a fixed precision.
