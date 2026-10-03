---
id: 25678
severity: "Medium"
---

# APRs are lower than they should

## Description



## Proof of Concept

## Vulnerability Detail

When borrowers borrow from LCG using [acceptFundsForAcceptBid](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L354>), they can choose the interest rate they are going to pay. Considering that borrowers will always choose the lowest APR available, loans are always made with `_interestRate >= getMinInterestRate()`.

However, [getMinInterestRate](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L769>) does not factor in the new amount that the borrower is going to borrow. Instead, it provides the pool's current APR. If the borrower borrows a significant amount of the pool, they will get a very favorable APR. This significantly reduces LP profits because the APR borrowers pay is always lower than the pool's current calculated interest.

Example:

1. APR ranges from 4% to 40% depending on utilization.
2. The pool currently has 70k principal, resulting in 70% utilization and an APR of `40% * 70% = 28%`.
3. Alice borrows 25k (25%) of the pool, raising utilization to 95%.
4. Despite the pool being at 95% utilization, Alice only pays 28% APR because her minimum interest was calculated without considering the newly borrowed amount.

LPs earn 28% APR from Alice's loan even though the pool is 95% utilized. If Alice borrowed 100%, the pool's maximum APR would have been 28% instead of 40% (as no more loans would be given and 28% would be the highest interest), resulting in LPs profits significantly decreasing.

## Impact

Lower interest and lower profits for LPs, making the maximum APR unreachable and breaking core functionality.

## Code Snippet

```solidity
    function getMinInterestRate() public view returns (uint16) {
        return interestRateLowerBound + uint16( uint256(interestRateUpperBound-interestRateLowerBound).percent(getPoolUtilizationRatio()) );
    }
```

## Recommendation

Include the newly borrowed amount in the interest calculation:

```diff
-   function getMinInterestRate() public view returns (uint16) {
-        return interestRateLowerBound + uint16( uint256(interestRateUpperBound-interestRateLowerBound).percent(getPoolUtilizationRatio()) );
-  }
-
+    function getMinInterestRate(uint256 newAmount) public view returns (uint16) {
+       uint256 utilization =  Math.min((totalPrincipalTokensLended - totalPrincipalTokensRepaid + newAmount) * 10000  / getPoolTotalEstimatedValue() , 10000 ));
+       return interestRateLowerBound + uint16( uint256(interestRateUpperBound-interestRateLowerBound).percent(utilization) );
+  }
```

If this seems too drastic, you could take the average APR of `before` and `after` the new borrowing and use that.
