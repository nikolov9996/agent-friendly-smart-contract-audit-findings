---
id: 21198
severity: "High"
---

# `BalancerConnector::_getPositionTVL` is calculated incorrectly

## Description

```solidity
BalancerConnector misuses the weight of pool tokens, leading to decreased TVL of these positions.
```

## Proof of Concept

```solidity
If we take a look at the balancer documentation and especially how the tokens are being valued, we can see that they are not using weight to determine the price of the `pool.tokens[pool.tokenIndex]`:

[BalancerDocs](https://docs.balancer.fi/reference/lp-tokens/valuing.html#directly-calculating-nav)
    
    (tokens, balances, lastChangeBlock) = vault.getPoolTokens(poolId);
    prices = fetchPricesFromPriceProvider(tokens); //ex. CoinGecko
    poolValueUsd = sum(balances[i]*price[i]);
    bptPriceUsd = poolValueUsd/bpt.totalSupply();

As we can see they are directly calculate the balance by the price, which is not the case in `Noya`:

[BalancerConnector.sol#L162-L173](https://github.com/code-423n4/2024-04-noya/blob/main/contracts/connectors/BalancerConnector.sol#L162-L173)
    
    function _getPositionTVL(HoldingPI memory p, address base) public view override returns (uint256) {
        PositionBP memory PTI = registry.getPositionBP(vaultId, p.positionId);
        PoolInfo memory pool = abi.decode(PTI.additionalData, (PoolInfo));
        uint256 lpBalance = totalLpBalanceOf(pool);
        (, uint256[] memory _tokenBalances,) = IBalancerVault(balancerVault).getPoolTokens(pool.poolId);
        uint256 _totalSupply = IERC20(pool.pool).totalSupply();
    
        uint256 _weight = pool.weights[pool.tokenIndex];
    
        uint256 token1bal = valueOracle.getValue(pool.tokens[pool.tokenIndex], base, _tokenBalances[pool.tokenIndex]);
        return (((1e18 * token1bal * lpBalance) / _weight) / _totalSupply);
    } 

The reason why weight is not needed here is because the balances returned from `getPoolTokens` are already split by them. If we look at the DAI-USDC-USDT pool we will see that balances returned are already splitted and there is no need to be divided by their weights. _(Note: please see image in warden’s[original submission](https://github.com/code-423n4/2024-04-noya-findings/issues/1033))_

But since Noya uses weights to divide the balance of the tokens, the result will be amount which is percentage weight, set in the `pool.weights[pool.tokenIndex]`, of the actual balance and TVL will be accounted much lower as it is in reality.

Example with USDT and values from [`BalancerConnector.t.sol`](https://github.com/code-423n4/2024-04-noya/blob/main/testFoundry/BalancerConnector.t.sol#L96-L125):

`return (((1e18 * 423099282190 * 991435857075096399976) / 333333333333333333) / 2596148431740844293012911818494888)` ≈ 0.484
```

## Recommendation

```solidity
Do not use weights to evaluate the TVL of the position, instead just refactor the `_getPositionTVL`’s return with proper decimal scaling based on the asset used.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect calculation of the total value locked (TVL) for Balancer LP positions inside the BalancerConnector contract. The function that returns the TVL multiplies the token value by the LP balance and then divides by the token weight before dividing by the pool total supply. Balancer’s vault already returns token balances that are proportional to their weights, so applying the weight a second time artificially reduces the computed amount to roughly the weight fraction of the true balance. This double‑weighting occurs whenever _getPositionTVL is called for a weighted pool, which includes most multi‑asset Balancer pools. An attacker or a user can observe that the reported TVL is far lower than the actual market value of the underlying assets; the protocol that relies on this figure for collateral checks, liquidation thresholds, or reward distribution will therefore treat the position as under‑collateralised. In practice a user may see their LP position value displayed as a fraction of a cent, may be unable to withdraw the expected amount, or may be liquidated despite holding sufficient assets. The issue was discovered during a security audit by comparing the Balancer documentation, which shows that TVL should be calculated as the sum of balances multiplied by price divided by total supply, with the connector’s implementation that incorrectly incorporates the weight field. Because the contract does not emit an explicit error and only returns a smaller number, the problem can be subtle and may only be noticed when users compare on‑chain values with external price feeds. The bug belongs to the class of financial‑formula errors where a parameter is applied twice, leading to an accounting mismatch. The correct fix is to remove the weight division and compute TVL using the raw token balances with proper decimal scaling, matching the Balancer reference implementation. By doing so the reported TVL will reflect the true market value, preventing false liquidation and ensuring accurate accounting.
