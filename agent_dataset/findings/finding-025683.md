---
id: 25683
severity: "Medium"
---

# LenderCommitmentGroup pools will have incorrect exchange rate when fee-on-transfer tokens are used

## Description



## Proof of Concept

## Vulnerability Detail

`LenderCommitmentGroup_Smart` is a contract that acts as it's own loan committment, which has liquidity pools with `principal token` and `collateral token`. Users can deposit `principal tokens` in exchange for `share tokens`.

Here is the flow of depositing principal tokens for shares

`LenderCommitmentGroup_Smart::addPrincipalToCommitmentGroup` []()

```javascript
    function addPrincipalToCommitmentGroup(
        uint256 _amount,
        address _sharesRecipient
    ) external returns (uint256 sharesAmount_) {

        // @audit if token is Fee-on-transfer, `_amount` transferred will be less
        principalToken.transferFrom(msg.sender, address(this), _amount);

@>      sharesAmount_ = _valueOfUnderlying(_amount, sharesExchangeRate());

        // @audit this will be inflated
        totalPrincipalTokensCommitted += _amount;

        // @audit Bob is minted shares dependent on original amount, not amount after transfer
        poolSharesToken.mint(_sharesRecipient, sharesAmount_);
    }
```

```javascript
    function sharesExchangeRate() public view virtual returns (uint256 rate_) {
        //@audit As more FOT tokens are deposited, this value becomes inflated
        uint256 poolTotalEstimatedValue = getPoolTotalEstimatedValue();

        // @audit EXCHANGE_RATE_EXPANSION_FACTOR = 1e36
        if (poolSharesToken.totalSupply() == 0) {
            return EXCHANGE_RATE_EXPANSION_FACTOR; // 1 to 1 for first swap
        }

        rate_ =
            (poolTotalEstimatedValue * EXCHANGE_RATE_EXPANSION_FACTOR) /
            poolSharesToken.totalSupply();
    }
```

```javascript
    function _valueOfUnderlying(
        uint256 amount,
        uint256 rate
    ) internal pure returns (uint256 value_) {
        if (rate == 0) {
            return 0;
        }

        value_ = (amount * EXCHANGE_RATE_EXPANSION_FACTOR) / rate;
    }
```

As you can see, the original `_amount` entered is used to not only issue the shares, but to keep track of the amount pool has:

```javascript
    function getPoolTotalEstimatedValue()
        public
        view
        returns (uint256 poolTotalEstimatedValue_)
    {
        // @audit This will be inflated
        int256 poolTotalEstimatedValueSigned = int256(
            totalPrincipalTokensCommitted
        ) +
            int256(totalInterestCollected) +
            int256(tokenDifferenceFromLiquidations) -
            int256(totalPrincipalTokensWithdrawn);

        poolTotalEstimatedValue_ = poolTotalEstimatedValueSigned > int256(0)
            ? uint256(poolTotalEstimatedValueSigned)
            : 0;
    }
```

If `poolTotalEstimatedValue` is inflated, then the exchange rate will be incorrect.

## Impact

As mentioned above, incorrect exchange rate calculation. Users will not receive the correct amount of shares/PT when withdrawing/depositing

## Code Snippet

[https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L307](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L307>)

## Recommendation

Check balance before and after transferring, then update accounting.
