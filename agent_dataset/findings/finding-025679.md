---
id: 25679
severity: "Medium"
---

# LenderCommitmentGroup_Smart does not use mulDiv when converting between token and share amounts, possibly leading to DoS or loss of funds

## Description



## Proof of Concept

## Vulnerability Detail

`sharesExchangeRate()` is calculated as

```solidity
rate_ =
            (poolTotalEstimatedValue  *
                EXCHANGE_RATE_EXPANSION_FACTOR) /
            poolSharesToken.totalSupply();`
```

which overflows if `poolTotalEstimatedValue > (2^256 - 1) / 1e36`. The readme mentions that any `ERC20` token that is supported by a Uniswap pool is supported, which means that if a token has decimals of, for example, `1e36`, the calculation above may easily overflow. In this case, `rate_ = realPoolTotalEstimatedValue  1e36  1e36 = realPoolTotalEstimatedValue * 1e72`, where `realPoolTotalEstimatedValue` is the number of tokens without the decimals part. Thus, the number of tokens needed to overflow would be `(2^256 - 1) / 1e72 = 115792`, which at a price of $1 is just `115792 USD`.

This bug is also present in `_valueOfUnderlying()`, which returns `value_ = (amount * EXCHANGE_RATE_EXPANSION_FACTOR) / rate;`.

## Impact

DoS of `LenderCommitmentGroup_Smart`, possibly with stuck tokens if users call `addPrincipalToCommitmentGroup()` with smaller amount at a time that do not cause an overflow when calculating `sharesExchangeRate()` and `_valueOfUnderlying()`, but would overflow when withdrawing in the calculation of `sharesExchangeRate()`, as `poolTotalEstimatedValue` could have increased to the value that overflows.

## Code Snippet

[sharesExchangeRate()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L262>)

```solidity
function sharesExchangeRate() public view virtual returns (uint256 rate_) {
    ...
    rate_ =
        (poolTotalEstimatedValue  *
            EXCHANGE_RATE_EXPANSION_FACTOR) /
        poolSharesToken.totalSupply();
}
```

[_valueOfUnderlying()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L324>)

```solidity
function _valueOfUnderlying(uint256 amount, uint256 rate)
    internal
    pure
    returns (uint256 value_)
{
    ...
    value_ = (amount * EXCHANGE_RATE_EXPANSION_FACTOR) / rate;
}
```

## Recommendation

Use `Math::mulDiv` from [OpenZeppelin](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/Math.sol>).
