---
id: 1211
severity: "High"
---

# `VaderRouter.calculateOutGivenIn` calculates wrong swap

## Description

The 3-path hop in `VaderRouter.calculateOutGivenIn` is supposed to first swap **foreign** assets to native assets **in pool0**, and then the received native assets to different foreign assets again **in pool1**.

The first argument of `VaderMath.calculateSwap(amountIn, reserveIn, reserveOut)` must refer to the same token as the second argument `reserveIn`. The code however mixes these positions up and first performs a swap in `pool1` instead of `pool0`:

```solidity
function calculateOutGivenIn(uint256 amountIn, address[] calldata path)
    external
    view
    returns (uint256 amountOut)
{
  if(...) {
  } else {
    return
        VaderMath.calculateSwap(
            VaderMath.calculateSwap(
                // @audit the inner trade should not be in pool1 for a forward swap. amountIn foreign => next param should be foreignReserve0
                amountIn,
                nativeReserve1,
                foreignReserve1
            ),
            foreignReserve0,
            nativeReserve0
        );
  }
```

```solidity
/** @audit instead should first be trading in pool0!
  VaderMath.calculateSwap(
      VaderMath.calculateSwap(
          amountIn,
          foreignReserve0,
          nativeReserve0
      ),
      nativeReserve1,
      foreignReserve1
  );
*/
```

## Proof of Concept

no poc

## Recommendation

Return the following code instead which first trades in `pool0` and then in `pool1`:

```solidity
return
  VaderMath.calculateSwap(
      VaderMath.calculateSwap(
          amountIn,
          foreignReserve0,
          nativeReserve0
      ),
      nativeReserve1,
      foreignReserve1
  );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the swap‑output calculation performed by the function that implements a two‑hop trade in the router contract. When a user wants to exchange a foreign token for another foreign token via an intermediate native token, the router is supposed to first calculate the amount obtained from swapping the input foreign token against the native reserve in the first liquidity pool (pool0), and then use that intermediate amount to calculate the final output from swapping the native token against the second foreign reserve in the second pool (pool1). The implementation mistakenly passes the reserve values of the second pool to the inner calculation call, effectively performing the first virtual swap in pool1 instead of pool0. As a result, the formula uses a mismatched reserve pair (nativeReserve1 and foreignReserve1) for the initial trade, which does not reflect the actual market depth of the first pool. This mis‑ordering produces an incorrect estimate of the amount that will be received, typically undervaluing the output for the user. The error is subtle because the function is a view‑only read‑only calculation; it does not revert or emit an event, and the returned number may still look plausible for certain inputs, making the flaw hard to detect without explicit comparison to the expected constant‑product formula. The issue manifests whenever the router processes a forward swap that follows a foreign‑to‑native‑to‑foreign three‑path route, i.e., when the path length triggers the else‑branch that contains the nested calculateSwap calls. Any participant relying on the router’s quoted output – such as end‑users submitting transactions, front‑ends displaying expected returns, or other contracts that depend on the quoted amount – can be misled into sending a transaction that yields fewer tokens than anticipated, effectively causing a loss of value. The bug was discovered during a manual security audit where the auditor examined the parameter ordering of the mathematical helper and identified the swap being applied to the wrong pool. Because the function only returns a computed number, the deviation does not raise an exception, which explains why the problem can remain unnoticed in routine testing. To remediate the issue, the router must first invoke the helper with the reserves of the first pool (foreignReserve0 and nativeReserve0) and only afterwards call the helper with the reserves of the second pool (nativeReserve1 and foreignReserve1). This restores the intended order of operations and aligns the calculation with the actual token flow, thereby eliminating the inaccurate output and ensuring that users receive the amount they expect based on the true pool reserves.
