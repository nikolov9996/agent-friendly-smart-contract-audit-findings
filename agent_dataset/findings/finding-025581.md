---
id: 25581
severity: "Crit/High"
---

# Withdrawals logic allows MEV exploits of TVL changes and zero-slippage zero-fee swaps

## Description



## Proof of Concept

**Scenario 1 (MEV, price increase):**

1. A transaction that will increase the TVL value without minting or burning ezETH, such as a Chainlink oracle update or EigenLayer rewards withdrawal, is observed.
2. An attacker sandwiches the transaction by depositing asset A right before it (minting ezETH to themselves).
3. The attacker completes the sandwich by submitting a withdrawal request for asset A after the "target" transaction. This sends the ezETH to `WithdrawQueue`, and credits the attacker with a larger amount of A than was just deposited, corresponding to the updated price of ezETH.
4. The attacker realizes an immediate, same block profit - a larger amount of the same asset, due to the price increase and credit of future withdrawal amount, and no fee being charged.
5. Value that would otherwise be distributed to holders of ezETH was lost to the attacker.

**Scenario 2 (malicious):**

1. Asset A experiences a sharp price decline due to slashing, exploit, or other factors.
2. An attacker borrows LST asset A from on-chain lending protocols. This is done to reduce the assets available for others to short the price manipulation of the next step.
3. The attacker buys up even more of the LST on CEX and DEX, running up the price of that asset, such that a manipulated price is reported by oracles.
4. The attacker deposits all asset A into Renzo, being credited with an outsized amount of ezETH due to the inflated price of the collateral.
5. The attacker immediately submits a withdrawal request of asset B, which upon conversion uses the inflated value of asset A in Renzo's TVL.
6. 7 days later, upon withdrawal claiming, the attacker withdraws the inflated amount of asset B.

**Scenario 3 (MEV, price decrease, zero-slippage zero-fees DEX):**

1. A supported LST experiences a sudden change in price due to factors such as price manipulation, an exploit of that LST, consensus layer penalties (slashing), or liquidity issues.
2. Existing external holders of the LST, or arbitrageurs borrowing the asset, frontrun the transaction that changes the oracle price by depositing the LST into Renzo, and immediately requesting a withdrawal of another asset (e.g., native ETH or another LST). Using Renzo as a zero-slippage oracle-price-based DEX.
3. After the withdrawal delay, the attackers claim their withdrawal, receiving the other asset at the pre-change price, effectively exploiting the ezETH holders.

## Impact

The newly introduced frontrunning vector, due to incurring only gas fees, and no fee that is proportional to the size of the "trade", allows profitably exploiting most TVL and oracle price changes, and exploiting previously exploitable updates (via Balancer's [usage of `getRate()`](<https://github.com/code-423n4/2024-04-renzo/blob/main/contracts/RateProvider/BalancerRateProvider.sol#L28C1-L41C6>)) and even more profitably via the new vector.

The impact is that value, that otherwise should be distributed to ezETH holders, is constantly lost to MEV.

Additionally, ezETH holders lose value due to facilitating asset swaps with no slippage and no fees based on outdated oracle prices.

## Recommendation

The redemption conversion should be performed at both request and claim time. If it results in a lower redeem value, that value should be used for the claim instead of the initial redeem amount. Additionally, a rate limit or a short delay on deposits with similar protection can be added as well.

```diff
function claim(uint256 withdrawRequestIndex) external nonReentrant {
    ...
+   // All the code converting from ezETH amount to amountToRedeem as is done in withdraw()

+   if (amountToRedeem < _withdrawRequest.amountToRedeem) {
+       _withdrawRequest.amountToRedeem = amountToRedeem;
+   }
}
```
