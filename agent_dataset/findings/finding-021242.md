---
id: 21242
severity: "High"
---

# Incorrect withdraw queue balance in TVL calculation

## Description

When calculating TVL it iterates over all the operator delegators and inside it iterates over all the collateral tokens.

```solidity
for (uint256 i = 0; i < odLength; ) {
    ...

    // Iterate through the tokens and get the value of each
    uint256 tokenLength = collateralTokens.length;
    for (uint256 j = 0; j < tokenLength; ) {
        ...

        // record token value of withdraw queue
        if (!withdrawQueueTokenBalanceRecorded) {
            totalWithdrawalQueueValue += renzoOracle.lookupTokenValue(
                collateralTokens[i],
                collateralTokens[j].balanceOf(withdrawQueue)
            );
        }

        unchecked {
            ++j;
        }
    }

    ...

    unchecked {
        ++i;
    }
}
```

However, the balance of `withdrawQueue` is incorrectly fetched, specifically this line:

```solidity
totalWithdrawalQueueValue += renzoOracle.lookupTokenValue(
    collateralTokens[i],
    collateralTokens[j].balanceOf(withdrawQueue)
);
```

It uses an incorrect index of the outer loop `i` to access the `collateralTokens`. `i` belongs to the operator delegator index, thus the returned value will not represent the real value of the token. For instance, if there is 1 OD and 3 collateral tokens, it will add the balance of the first token 3 times and neglect the other 2 tokens. If there are more ODs than collateral tokens, the the execution will revert (index out of bounds).

This calculation impacts the TVL which is the essential data when calculating mint/redeem and other critical values. A miscalculation in TVL could have devastating results.

## Proof of Concept

A simplified version of the function to showcase that the same token (in this case `address(1)`) is emitted multiple times and other tokens are untouched:

```solidity
contract RestakeManager {

    address[] public operatorDelegators;

    address[] public collateralTokens;

    event CollateralTokenLookup(address token);

    constructor() {
        operatorDelegators.push(msg.sender);

        collateralTokens.push(address(1));
        collateralTokens.push(address(2));
        collateralTokens.push(address(3));
    }

    function calculateTVLs() public {
        // Iterate through the ODs
        uint256 odLength = operatorDelegators.length;

        for (uint256 i = 0; i < odLength; ) {
            // Iterate through the tokens and get the value of each
            uint256 tokenLength = collateralTokens.length;
            for (uint256 j = 0; j < tokenLength; ) {
                emit CollateralTokenLookup(collateralTokens[i]);

                unchecked {
                    ++j;
                }
            }

            unchecked {
                ++i;
            }
        }
    }
}
```

## Recommendation

Change to `collateralTokens[j]`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an indexing error that occurs while the contract aggregates the value of tokens held in the withdraw queue for Total Value Locked (TVL) calculation. The outer loop iterates over operator delegators (indexed by i) and the inner loop iterates over collateral tokens (indexed by j). Inside the inner loop the code mistakenly uses the outer index i to select a token from the collateralTokens array when calling balanceOf on the withdraw queue. Because i refers to a delegator, the contract repeatedly reads the balance of the first token for every token iteration and completely ignores the balances of the remaining tokens. When there is a single delegator and three tokens, the balance of token 0 is added three times, inflating the TVL, while the balances of token 1 and token 2 are never counted. If the number of delegators exceeds the number of tokens, the out‑of‑bounds access causes a revert, aborting the calculation. The root cause is a simple loop‑variable mix‑up, a classic off‑by‑one or wrong‑index bug that leads to an incorrect aggregation of financial data. An attacker can exploit the inflated TVL by minting new protocol tokens at a rate that assumes more collateral than actually exists, or by redeeming against a TVL that under‑represents the true collateral, potentially draining the system or causing under‑collateralisation. The impact is high because TVL is used to price mint and redeem operations, to calculate rewards, and to display protocol health on user interfaces; a mis‑reported TVL can cause users to receive more tokens than they should, see unexpected zero balances, or observe the protocol UI showing a total value that does not match the real assets. The bug manifests whenever the calculateTVL function runs with at least one operator delegator and more than one collateral token, which is the normal operating condition for the protocol. All participants—token holders, liquidity providers, and the protocol itself—are affected because the financial guarantees rely on an accurate TVL figure. The issue was discovered during a manual audit by Code4rena, where a proof‑of‑concept contract emitted the same token address repeatedly, revealing that the inner loop was using the wrong index. The problem is subtle because TVL is an aggregate metric; the discrepancy may only become apparent under extreme conditions or when users notice mismatched mint/redeem amounts. To fix the issue the contract should reference collateralTokens[j] when querying the withdraw queue balance, ensuring each token’s actual balance is added exactly once. This correction aligns the aggregation logic with the intended accounting model, restores accurate TVL reporting, and prevents the downstream pricing errors that could otherwise compromise protocol safety.
