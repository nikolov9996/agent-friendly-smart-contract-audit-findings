---
id: 25757
severity: "Medium"
---

# Vault::withdraw() withdraws too much liquidity leading to idle capital and loss of fees

## Description



## Proof of Concept

```solidity
function withdraw(uint256 shares, uint256 minAmount0, uint256 minAmount1)
    public
    returns (uint256 withdrawAmount0, uint256 withdrawAmount1)
{
    IStrategy(strategy).collectFees();

    (uint256 totalBalance0, uint256 totalBalance1) = IStrategy(strategy).balances();

    uint256 totalSupply = totalSupply();
    _burn(msg.sender, shares);

    withdrawAmount0 = totalBalance0 * shares / totalSupply;
    withdrawAmount1 = totalBalance1 * shares / totalSupply;

    (uint256 idle0, uint256 idle1) = IStrategy(strategy).idleBalances();

    if (idle0 < withdrawAmount0 || idle1 < withdrawAmount1) {
        // When withdrawing partial, there might be a few wei difference.
        (withdrawAmount0, withdrawAmount1) = IStrategy(strategy).withdrawPartial(shares, totalSupply);
    }
```

## Recommendation

Reduce the shares to withdraw from the strategy by the liquidity already available (idle).
