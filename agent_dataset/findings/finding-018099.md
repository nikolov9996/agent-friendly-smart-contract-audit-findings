---
id: 18099
severity: "High"
---

# The `collect` function transfers zero fees due to incorrect execution order

## Description

Detailed description of the impact of this finding. The `collect()` function will always transfer ZERO fees. At the same time, non-zero `_feesPosition` will be burned.

```
_feesPositions[id][msg.sender].burn(long0Fees, long1Fees, shortFees);
```

As a result, the contracts will be left in an inconsistent state. The user will burn `_feesPositions` without receiving the fees!

## Proof of Concept

Provide direct links to all referenced code in GitHub. Add screenshots, logs, or any other relevant proof that illustrates the concept.

The `collect()` function will always transfer ZERO fees in the following line:

```solidity
// transfer the fees amount to the recipient
ITimeswapV2Pool(poolPair).transferFees(param.strike, param.maturity, param.to, long0Fees, long1Fees, shortFees);
```

This is because, at this moment, the values of `long0Fees`, `long1Fees`, `shortFees` have not been calculated yet, actually, they will be equal to zero. Therefore, no fees will be transferred. The values of `long0Fees`, `long1Fees`, `shortFees` are calculated afterwards by the following line:

```solidity
(long0Fees, long1Fees, shortFees) = _feesPositions[id][msg.sender].getFees(param.long0FeesDesired, param.long1FeesDesired, param.shortFeesDesired);
```

Therefore, `ITimeswapV2Pool(poolPair).transferFees` must be called after this line to be correct.

## Recommendation

We moved the line `ITimeswapV2Pool(poolPair).transferFees` after `long0Fees`, `long1Fees`, `shortFees` have been calculated first.

```solidity
function collect(TimeswapV2LiquidityTokenCollectParam calldata param) external returns (uint256 long0Fees, uint256 long1Fees, uint256 shortFees, bytes memory data) {
    ParamLibrary.check(param);

    bytes32 key = TimeswapV2LiquidityTokenPosition({token0: param.token0, token1: param.token1, strike: param.strike, maturity: param.maturity}).toKey();

    // start the reentrancy guard
    raiseGuard(key);

    (, address poolPair) = PoolFactoryLibrary.getWithCheck(optionFactory, poolFactory, param.token0, param.token1);

    uint256 id = _timeswapV2LiquidityTokenPositionIds[key];

    _updateFeesPositions(msg.sender, address(0), id);

    (long0Fees, long1Fees, shortFees) = _feesPositions[id][msg.sender].getFees(param.long0FeesDesired, param.long1FeesDesired, param.shortFeesDesired);

    if (param.data.length != 0)
        data = ITimeswapV2LiquidityTokenCollectCallback(msg.sender).timeswapV2LiquidityTokenCollectCallback(
            TimeswapV2LiquidityTokenCollectCallbackParam({
                token0: param.token0,
                token1: param.token1,
                strike: param.strike,
                maturity: param.maturity,
                long0Fees: long0Fees,
                long1Fees: long1Fees,
                shortFees: shortFees,
                data: param.data
            })
        );

    // transfer the fees amount to the recipient
    ITimeswapV2Pool(poolPair).transferFees(param.strike, param.maturity, param.to, long0Fees, long1Fees, shortFees);

    // burn the desired fees from the fees position
    _feesPositions[id][msg.sender].burn(long0Fees, long1Fees, shortFees);

    if (long0Fees != 0 || long1Fees != 0 || shortFees != 0) _removeTokenEnumeration(msg.sender, address(0), id, 0);

    // stop the reentrancy guard
    lowerGuard(key);
}
```

> Fixed in [PR](https://github.com/Timeswap-Labs/Timeswap-V2-Monorepo/pull/256).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an execution‑order flaw in the collect function of the Timeswap V2 liquidity token contract. The function is intended to calculate the accrued fees for a user, transfer those fees to a recipient, and then burn the corresponding fee position. However, the contract calls the external pool’s transferFees method before it has retrieved the actual fee amounts from the internal fees position. At the moment of the transfer call the variables long0Fees, long1Fees and shortFees are still zero, so the pool transfers a zero‑value fee payload. Immediately afterwards the contract queries the fees position, obtains the non‑zero amounts, and then burns those amounts from the user’s fee balance. As a result the user’s fee position is reduced while no fees are actually paid out, leaving the protocol state inconsistent and causing a loss of value for liquidity providers. The bug occurs every time the collect function is invoked, regardless of the requested fee amounts, because the ordering of the getFees call and the transferFees call is fixed in the source. It was discovered during a formal audit when the auditors observed that the transferFees line used variables that had not yet been assigned. The issue is subtle because the transaction does not revert and appears successful; only after the call the user’s fee balance is zero and no funds are received, which can be missed without explicit balance checks. This class of bug belongs to incorrect sequencing of state‑changing operations that leads to zero‑value external calls and unintended state mutation. From a user perspective the UI shows a successful collect transaction, but the expected fee payout is missing and the fee token balance disappears, violating the expectation that a collect call returns the accrued fees. The proper fix is to reorder the logic: first compute the fee amounts by calling getFees, then invoke transferFees with the computed values, and finally burn the fees from the position. This ensures that the transferred amount matches the burned amount and preserves accounting integrity.
