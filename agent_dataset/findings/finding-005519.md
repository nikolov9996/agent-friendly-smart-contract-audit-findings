---
id: 5519
severity: "High"
---

# Specified amount is not updated after clamping, causing a lock of funds

## Description

The value of amountSpecified in the MarginalV1LBPool.swap() function is not updated after the price is clamped. The clamping narrows the price movement during the swap, but the user still pays the full specified amount. The extra tokens cannot be withdrawn by the supplier and are left locked in the contract.
The swapping logic in the MarginalV1LBPool.swap() function allows swapping only until the either the lower or the upper price is reached.
The target price of a swap is computed using the SqrtPriceMath.sqrtPriceX96NextSwap() function so that it's not lower than the lower price and not higher than the upper price.
However, after a price was clamped, the specified input amount was not recalculated (MarginalV1LBPool.sol#L306-L307, MarginalV1LBPool.sol#L328-L329):
```solidity
if (!zeroForOne) {
    amount0 = !exactInput ? amountSpecified : amount0; // in case of rounding issues
    amount1 = exactInput ? amountSpecified : amount1;
// ...
} else {
    amount1 = !exactInput ? amountSpecified : amount1; // in case of rounding issues
    amount0 = exactInput ? amountSpecified : amount0;
// ...
```
Clamping reduces the price movement required to achieve the target price, thus also reducing the required input amount. However, the user still pays the full amountSpecified.
The final price is set to the clamped price (MarginalV1LBPool.sol#L351-L352):
```solidity
// lbp done if reaches final sqrt price
_state.finalized = (_state.sqrtPriceX96 == sqrtPriceFinalizeX96);
```
When finalizing and burning liquidity, the amounts of tokens withdrawn from the pool are computed within the lower and upper price range (MarginalV1LBPool.sol#L449-L455):
```solidity
// amounts out adjusted for concentrated range position price limits
(amount0, amount1) = RangeMath.toAmounts(
    liquidityDelta,
    _state.sqrtPriceX96,
    sqrtPriceLowerX96,
    sqrtPriceUpperX96
);
```
But since the trader pays more tokens than required to move the price between the boundaries of the range, one of the computed amounts will be smaller than the amount of tokens paid by the trader. It won't be possible to withdraw the difference and it will remain in the contract.
Impact: A portion of tokens paid by users is locked in the contract and cannot be withdrawn during pool finalization.
Likelihood: The vulnerability impacts all swaps that reach the final price, but since finalizing pools doesn't require reaching it, the likelihood is medium.

## Proof of Concept

The following proof of concept demonstrates that the specified input amount is paid in full when clamping happens:
• tests/functional/pool/test_pool_swap.py:
```solidity
@pytest.mark.parametrize("init_with_sqrt_price_lower_x96", [False])
@pytest.mark.focus
def test_pool_swap__updates_state_with_exact_input_zero_for_one_to_range_tick_clamping(
    pool_initialized,
    callee,
    sqrt_price_math_lib,
    swap_math_lib,
    liquidity_math_lib,
    sender,
    alice,
    token0,
    token1,
    chain,
    init_with_sqrt_price_lower_x96,
):
    pool_initialized_with_liquidity = pool_initialized(init_with_sqrt_price_lower_x96)
    state = pool_initialized_with_liquidity.state()
    sqrt_price_lower_x96 = pool_initialized_with_liquidity.sqrtPriceLowerX96()
    sqrt_price_finalize_x96 = pool_initialized_with_liquidity.sqrtPriceFinalizeX96()
    zero_for_one = True
    sqrt_price_limit_x96 = MIN_SQRT_RATIO + 1
    # calc amounts in/out for the swap with first pass on price thru sqrt price math lib
    sqrt_price_x96_next = sqrt_price_lower_x96
    (amount0, amount1) = swap_math_lib.swapAmounts(
        state.liquidity,
        state.sqrtPriceX96,
        sqrt_price_x96_next,
    )
    amount_specified = int(amount0 * 1.001)
    # extra buffer
    # compute the target price, as it's done in Pool.swap
    sqrt_price_x96_next_computed = sqrt_price_math_lib.sqrtPriceX96NextSwap(
        state.liquidity,
        state.sqrtPriceX96,
        zero_for_one,
        amount_specified,
    )
    # update the oracle
    block_timestamp_next = chain.pending_timestamp
    tick_cumulative = state.tickCumulative + state.tick * (
        block_timestamp_next - state.blockTimestamp
    )
    state.blockTimestamp = block_timestamp_next
    state.tickCumulative = tick_cumulative
    # update state price
    state.sqrtPriceX96 = sqrt_price_x96_next
    state.tick = calc_tick_from_sqrt_price_x96(sqrt_price_x96_next)
    state.finalized = sqrt_price_x96_next == sqrt_price_finalize_x96
    tx = callee.swap(
        pool_initialized_with_liquidity.address,
        alice.address,
        zero_for_one,
        amount_specified,
        sqrt_price_limit_x96,
        sender=sender,
    )
    assert pool_initialized_with_liquidity.state() == state
    assert state.finalized
    # the swap price was clamped: the computed price is below the actual price
    assert sqrt_price_x96_next_computed < state.sqrtPriceX96
    # the input amount wasn't clamped and remained as specified by the caller
    swap = tx.decode_logs(pool_initialized_with_liquidity.Swap)[0]
    assert amount_specified == swap.amount0
    assert amount1 == swap.amount1
```
The following proof of concept demonstrates that there are leftover tokens after pool finalization:
• tests/functional/test_supplier_finalize_pool.py:
```solidity
@pytest.mark.parametrize("fee_protocol", [10])
@pytest.mark.parametrize("init_with_sqrt_price_lower_x96", [False])
@pytest.mark.focus
def test_supplier_finalize_pool__finalizes_pool_leftover(
    factory,
    supplier,
    receiver_and_pool_finalized,
    token0,
    token1,
    sender,
    admin,
    finalizer,
    chain,
    fee_protocol,
    init_with_sqrt_price_lower_x96,
):
    factory.setFeeProtocol(fee_protocol, sender=admin)
    (receiver, pool_finalized_with_liquidity) = receiver_and_pool_finalized(
        init_with_sqrt_price_lower_x96
    )
    assert (
        pool_finalized_with_liquidity.sqrtPriceInitializeX96() > 0
    )
    # pool initialized
    assert pool_finalized_with_liquidity.totalSupply() > 0
    state = pool_finalized_with_liquidity.state()
    assert state.finalized is True
    assert state.feeProtocol == fee_protocol
    (receiver_reserve0, receiver_reserve1) = (receiver.reserve0(), receiver.reserve1())
    assert (
        receiver_reserve0 > 0
        if init_with_sqrt_price_lower_x96
        else receiver_reserve1 > 0
    )
    assert sender.address != finalizer.address
    deadline = chain.pending_timestamp + 3600
    params = (
        pool_finalized_with_liquidity.token0(),
        pool_finalized_with_liquidity.token1(),
        pool_finalized_with_liquidity.tickLower(),
        pool_finalized_with_liquidity.tickUpper(),
        pool_finalized_with_liquidity.blockTimestampInitialize(),
        deadline,
    )
    tx = supplier.finalizePool(params, sender=sender)
    total_supply = pool_finalized_with_liquidity.totalSupply()
    assert total_supply == 0
    state = pool_finalized_with_liquidity.state()
    assert state.liquidity == 0
    assert token0.balanceOf(pool_finalized_with_liquidity.address) == 422484836 # !!! leftover
    assert token1.balanceOf(pool_finalized_with_liquidity.address) == 1
```

## Recommendation

In the MarginalV1LBPool.swap() function, consider using both computed amount swap amounts after the target price was clamped.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an over‑payment and fund‑locking bug that occurs in the swap function of a concentrated‑liquidity pool when the target price is clamped to the lower or upper bound. The contract computes a next price using a price‑clamping routine, which may reduce the amount of input tokens required to reach the target. However, the code does not recalculate the amountSpecified after this clamping step, so the swap proceeds with the original input amount even though a smaller amount would have been sufficient. As a result the trader pays more tokens than needed, and when the pool is later finalized the withdrawal logic only accounts for the amount required to move the price within the range. The surplus tokens remain in the contract because there is no mechanism to withdraw them, effectively locking a portion of user funds. This issue manifests when a swap reaches the final price and the price calculation is clamped; users see that they sent the full amount they specified but receive a smaller amount out, and after pool finalization the contract balance contains unexpected leftover tokens. The bug was discovered through functional tests that compared the emitted swap amounts with the computed clamped price, revealing a mismatch. It can be hard to notice because the swap still succeeds and the pool appears to function, but the hidden surplus is only observable by inspecting contract balances after finalization. The problem belongs to the class of accounting‑logic errors where post‑condition values are not updated after a constraint adjustment, leading to incorrect fund accounting. To fix the issue the swap routine should recompute the required input amount after price clamping and use those adjusted values for the transfer and for the finalization calculations, ensuring that the amount withdrawn matches the amount actually paid.
