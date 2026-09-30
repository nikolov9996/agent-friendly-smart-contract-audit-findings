---
id: 1105
severity: "High"
---

# Ideal balance is not calculated correctly when providing imbalanced liquidity

## Description

When a user provides imbalanced liquidity, the fee is calculated according to the ideal balance. In saddle finance, the optimal balance should be the same ratio as in the Pool.

Take, for example, if there’s 10000 USD and 10000 DAI in the saddle’s USD/DAI pool, the user should get the optimal lp if he provides lp with ratio = 1.

However, if the `customSwap` pool is created with a target price = 2. The user would get 2 times more lp if he deposits DAI. [SwapUtils.sol#L1227-L1245](https://github.com/code-423n4/2021-11-bootfinance/blob/main/customswap/contracts/SwapUtils.sol#L1227-L1245) The current implementation does not calculates ideal balance correctly.

If the target price is set to be 10, the ideal balance deviates by 10. The fee deviates a lot. I consider this is a high-risk issues.

## Proof of Concept

We can observe the issue if we initiates two pools DAI/LINK pool and set the target price to be 4.

For the first pool, we deposit more DAI.

```solidity
swap = deploy_contract('Swap' 
    [dai.address, link.address], [18, 18], 'lp', 'lp', 1, 85, 10**7, 0, 0, 4* 10**18)
link.functions.approve(swap.address, deposit_amount).transact()
dai.functions.approve(swap.address, deposit_amount).transact()
previous_lp = lptoken.functions.balanceOf(user).call()
swap.functions.addLiquidity([deposit_amount, deposit_amount // 10], 10, 10**18).transact()
post_lp = lptoken.functions.balanceOf(user).call()
print('get lp', post_lp - previous_lp)
```

For the second pool, one we deposit more DAI.

```solidity
swap = deploy_contract('Swap' 
    [dai.address, link.address], [18, 18], 'lp', 'lp', 1, 85, 10**7, 0, 0, 4* 10**18)
link.functions.approve(swap.address, deposit_amount).transact()
dai.functions.approve(swap.address, deposit_amount).transact()
previous_lp = lptoken.functions.balanceOf(user).call()
swap.functions.addLiquidity([deposit_amount, deposit_amount // 10], 10, 10**18).transact()
post_lp = lptoken.functions.balanceOf(user).call()
print('get lp', post_lp - previous_lp)
```

We can get roughly 4x more lp in the first case

## Recommendation

The current implementation uses `self.balances`

```solidity
for (uint256 i = 0; i < self.pooledTokens.length; i++) {
    uint256 idealBalance = v.d1.mul(self.balances[i]).div(v.d0);
    fees[i] = feePerToken
        .mul(idealBalance.difference(newBalances[i]))
        .div(FEE_DENOMINATOR);
    self.balances[i] = newBalances[i].sub(
        fees[i].mul(self.adminFee).div(FEE_DENOMINATOR)
    );
    newBalances[i] = newBalances[i].sub(fees[i]);
}
```

Replaces `self.balances` with `_xp(self, newBalances)` would be a simple fix. I consider the team can take balance’s weighted pool as a reference. [WeightedMath.sol#L149-L179](https://github.com/balancer-labs/balancer-v2-monorepo/blob/7ff72a23bae6ce0eb5b134953cc7d5b79a19d099/pkg/pool-weighted/contracts/WeightedMath.sol#L149-L179)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from an incorrect calculation of the "ideal balance" during the fee assessment that occurs when a liquidity provider adds imbalanced amounts of tokens to a custom‑price pool. In the current implementation the fee is derived from the raw token balances stored in the pool (self.balances). However, for pools that use a target price different from 1, the correct reference point is the virtual, price‑scaled balance obtained via the _xp function. By using the unscaled balances, the contract under‑estimates the ideal balance for the token that is over‑represented relative to the target price, which in turn reduces the fee charged for the deposit. As a result, a user who deposits a skewed ratio of tokens receives far more LP tokens than the proportional share they should obtain. For example, in a pool with a target price of 4, depositing DAI in a 10 : 1 DAI/LINK ratio yields approximately four times the expected amount of LP tokens. The impact is that the protocol can issue excessive LP tokens, effectively allowing an attacker to acquire a larger ownership stake of the underlying assets without paying the appropriate fee. When the attacker later withdraws or swaps, they can extract assets at the correct market ratios, causing loss of funds for other liquidity providers and reducing the protocol’s revenue. This issue appears only when the pool’s target price deviates from the 1 : 1 ratio and when liquidity is supplied in an imbalanced fashion, making it easy to overlook during casual testing because balanced deposits calculate fees correctly. It was discovered during a security audit by comparing the LP minted from two identical pools with different target prices and observing a four‑fold increase in LP for the imbalanced case. The bug is hard to notice because the fee computation itself does not throw an error; the mis‑calculation simply yields a lower fee, which is visible only under specific price‑ratio conditions. To remediate, the fee loop should replace the direct use of self.balances with the virtual balances returned by _xp(self, newBalances), aligning the ideal balance with the weighted‑price model used by similar protocols (e.g., Balancer's WeightedMath). This change restores correct fee assessment and prevents the over‑issuance of LP tokens, preserving the intended accounting invariants of the pool.
