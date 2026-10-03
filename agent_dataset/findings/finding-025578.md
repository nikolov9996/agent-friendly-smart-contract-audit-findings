---
id: 25578
severity: "Crit/High"
---

# Incorrect withdraw queue balance in TVL calculation

## Description



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
