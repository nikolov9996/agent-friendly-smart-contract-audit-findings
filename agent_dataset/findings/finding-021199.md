---
id: 21199
severity: "High"
---

# `BalancerConnector` has incorrect implementation of totalSupply, positionTVL and total TVL will be invalid

## Description

```solidity
`BalancerConnector` has incorrect implementation of totalSupply, positionTVL and total TVL will be invalid.
```

## Proof of Concept

```solidity
In `BalancerConnector::_getPositionTVL`, when calculating connector held LP token ratio, `IERC20(pool.pool).totalSupply()` is called. This is an incorrect implementation.

In Balancer, totalSupply() is different from totalActualSupply(). Based on Balancer [doc](https://docs.balancer.fi/concepts/advanced/valuing-bpt/valuing-bpt.html#getactualsupply):

> getActualSupply: This is the most common/current function to call. getActualSupply is used by the most recent versions of Weighted and Stable Pools. It accounts for pre-minted BPT as well as due protocol fees.

> totalSupply: In general, totalSupply only makes sense to call for older “legacy” pools. The original Weighted and Stable Pools do not have pre-minted BPT, so they follow the typical convention of using totalSupply to account for issued pool shares.

In short, totalSupply will include pre-minted BPT(balancer pool tokens) and shouldn’t be used when calculating user position value. [The pool’s arithmetic behaves as if it didn’t exist, and the BPT total supply is not a useful value](https://docs.balancer.fi/concepts/advanced/preminted-bpt.html#preminted-bpt). `getAcutalSupply` should be used instead.
    
    //contracts/connectors/BalancerConnector.sol
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

(<https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/BalancerConnector.sol#L167>)

In addition, in BalancerConnecot.t.sol we can see the intention is to use weighted pools with pre-minted BPT([USDC-DAI-USDT Stable Pool](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/testFoundry/utils/resources/MainnetAddresses.sol#L150)).  
Based on the [deployed pool contract](https://etherscan.io/address/0x79c58f70905F734641735BC61e45c19dD9Ad60bC#readContract), `totalSupply` is 2596148430608596515167161432296901 . `totalAcutalSupply` is 1036029413274776191102780.
```

## Recommendation

```solidity
Use `IERC20(pool.pool).totalActualSupply()` with compatible pools.
```

> True, needs to be fixed. But not high severity I think.

> Considering as High Risk due to TVL impact share calculation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The BalancerConnector contract calculates a user position value and the overall protocol TVL by reading the ERC20 totalSupply of a Balancer pool token. In modern Balancer weighted and stable pools the token supply is split into a pre‑minted amount and the actual circulating amount that reflects protocol fees. The ERC20 totalSupply function returns the sum of both, while the correct metric for valuation is totalActualSupply (also called getActualSupply). Because the connector uses totalSupply, the denominator in the positionTVL formula is inflated, causing the computed TVL and individual share values to be lower than they should be. This mis‑calculation occurs whenever the connector interacts with pools that implement pre‑minted BPT, which includes most recent Balancer pools. Liquidity providers and any protocol component that relies on the reported TVL for fee distribution, reward allocation or risk assessment are affected. From a user perspective the UI may display a higher total pool value than what is actually withdrawable, withdrawals can return less than expected or even appear to be zero, and balances may seem to disappear after certain operations. The issue was discovered during a Code4rena audit that compared the connector code with Balancer documentation and observed a discrepancy between totalSupply and totalActualSupply on a live pool. The bug is subtle because totalSupply returns a plausible large number, making the error easy to miss unless the specific pool type is examined. The vulnerability belongs to the class of accounting errors caused by using an inappropriate supply metric, similar to using totalSupply of a rebasing token for valuation. To remediate, the connector should replace the call to IERC20(pool).totalSupply() with the pool’s totalActualSupply (or getActualSupply) function for compatible pools, and adjust the TVL calculation accordingly. This change restores the invariant that the denominator reflects only the circulating shares, ensuring accurate TVL reporting, correct reward distribution, and preventing users from receiving less than their rightful share.
