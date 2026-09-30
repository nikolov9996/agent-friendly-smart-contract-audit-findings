---
id: 18517
severity: "High"
---

# PositionManager’s `moveLiquidity` can freeze funds by removing destination index even when the move was partial

## Description

```solidity
positionIndex.remove(params_.fromIndex)`removes the PositionManager entry even when it is only partial removal as a result of `IPool(params_.pool).moveQuoteToken(...)` call.

I.e. it is correct to do `fromPosition.lps -= vars.lpbAmountFrom`, but the resulting amount might not be zero, moveQuoteToken() are not guaranteed to clear the position as it has available liquidity constraint. In the case of partial quote funds removal `positionIndex.remove(params_.fromIndex)` operation will freeze the remaining position.
```

## Proof of Concept

```solidity
While `positions[params_.tokenId][params_.fromIndex]` LP shares are correctly reduced by the amount returned by pool’s moveQuoteToken(), the position itself is unconditionally removed from the `positionIndexes[params_.tokenId]`, making any remaining funds unavailable:

        function moveLiquidity(
            MoveLiquidityParams calldata params_
        ) external override mayInteract(params_.pool, params_.tokenId) nonReentrant {
            Position storage fromPosition = positions[params_.tokenId][params_.fromIndex];
    
            MoveLiquidityLocalVars memory vars;
            vars.depositTime = fromPosition.depositTime;
    
            // handle the case where owner attempts to move liquidity after they've already done so
            if (vars.depositTime == 0) revert RemovePositionFailed();
    
            // ensure bucketDeposit accounts for accrued interest
            IPool(params_.pool).updateInterest();
    
            // retrieve info of bucket from which liquidity is moved  
            (
                vars.bucketLP,
                vars.bucketCollateral,
                vars.bankruptcyTime,
                vars.bucketDeposit,
            ) = IPool(params_.pool).bucketInfo(params_.fromIndex);
    
            // check that bucket hasn't gone bankrupt since memorialization
            if (vars.depositTime <= vars.bankruptcyTime) revert BucketBankrupt();
    
            // calculate the max amount of quote tokens that can be moved, given the tracked LP
            vars.maxQuote = _lpToQuoteToken(
                vars.bucketLP,
                vars.bucketCollateral,
                vars.bucketDeposit,
                fromPosition.lps,
                vars.bucketDeposit,
                _priceAt(params_.fromIndex)
            );
    
            EnumerableSet.UintSet storage positionIndex = positionIndexes[params_.tokenId];
    
            // remove bucket index from which liquidity is moved from tracked positions
            if (!positionIndex.remove(params_.fromIndex)) revert RemovePositionFailed();
    
            // update bucket set at which a position has liquidity
            // slither-disable-next-line unused-return
            positionIndex.add(params_.toIndex);
    
            // move quote tokens in pool
            (
                vars.lpbAmountFrom,
                vars.lpbAmountTo,
            ) = IPool(params_.pool).moveQuoteToken(
                vars.maxQuote,
                params_.fromIndex,
                params_.toIndex,
                params_.expiry
            );
    
            Position storage toPosition = positions[params_.tokenId][params_.toIndex];
    
            // update position LP state
            fromPosition.lps -= vars.lpbAmountFrom;
            toPosition.lps   += vars.lpbAmountTo;
            // update position deposit time to the from bucket deposit time
            toPosition.depositTime = vars.depositTime;

Bucket can contain a mix of quote and collateral tokens, but moveLiquidity() aims to retrieve `vars.maxQuote = _lpToQuoteToken(...)` quote funds per current exchange rate:

        function _lpToQuoteToken(
            uint256 bucketLP_,
            uint256 bucketCollateral_,
            uint256 deposit_,
            uint256 lenderLPBalance_,
            uint256 maxQuoteToken_,
            uint256 bucketPrice_
        ) pure returns (uint256 quoteTokenAmount_) {
            uint256 rate = Buckets.getExchangeRate(bucketCollateral_, bucketLP_, deposit_, bucketPrice_);

            quoteTokenAmount_ = Maths.wmul(lenderLPBalance_, rate);

            if (quoteTokenAmount_ > deposit_)       quoteTokenAmount_ = deposit_;
            if (quoteTokenAmount_ > maxQuoteToken_) quoteTokenAmount_ = maxQuoteToken_;
        }

There might be not enough quote deposit funds available to redeem the whole quote amount requested, which is controlled by the corresponding liquidity constraint:

            uint256 scaledLpConstraint = Maths.wmul(params_.lpConstraint, exchangeRate);
            if (
                params_.depositConstraint < scaledDepositAvailable &&
                params_.depositConstraint < scaledLpConstraint
            ) {
                // depositConstraint is binding constraint
                removedAmount_ = params_.depositConstraint;
                redeemedLP_    = Maths.wdiv(removedAmount_, exchangeRate);
            }
```

## Recommendation

```solidity
As a most straightforward solution consider reverting when there is a remainder, i.e. when `fromPosition.lps > dust_threshold`:

        function moveLiquidity(
            MoveLiquidityParams calldata params_
        ) external override mayInteract(params_.pool, params_.tokenId) nonReentrant {
            Position storage fromPosition = positions[params_.tokenId][params_.fromIndex];
    
            MoveLiquidityLocalVars memory vars;
            vars.depositTime = fromPosition.depositTime;
    
            // handle the case where owner attempts to move liquidity after they've already done so
            if (vars.depositTime == 0) revert RemovePositionFailed();
    
            // ensure bucketDeposit accounts for accrued interest
            IPool(params_.pool).updateInterest();
    
            // retrieve info of bucket from which liquidity is moved  
            (
                vars.bucketLP,
                vars.bucketCollateral,
                vars.bankruptcyTime,
                vars.bucketDeposit,
            ) = IPool(params_.pool).bucketInfo(params_.fromIndex);
    
            // check that bucket hasn't gone bankrupt since memorialization
            if (vars.depositTime <= vars.bankruptcyTime) revert BucketBankrupt();
    
            // calculate the max amount of quote tokens that can be moved, given the tracked LP
            vars.maxQuote = _lpToQuoteToken(
                vars.bucketLP,
                vars.bucketCollateral,
                vars.bucketDeposit,
                fromPosition.lps,
                vars.bucketDeposit,
                _priceAt(params_.fromIndex)
            );
    
            EnumerableSet.UintSet storage positionIndex = positionIndexes[params_.tokenId];
    
            // remove bucket index from which liquidity is moved from tracked positions
            if (!positionIndex.remove(params_.fromIndex)) revert RemovePositionFailed();
    
            // update bucket set at which a position has liquidity
            // slither-disable-next-line unused-return
            positionIndex.add(params_.toIndex);
    
            // move quote tokens in pool
            (
                vars.lpbAmountFrom,
                vars.lpbAmountTo,
            ) = IPool(params_.pool).moveQuoteToken(
                vars.maxQuote,
                params_.fromIndex,
                params_.toIndex,
                params_.expiry
            );
    
            Position storage toPosition = positions[params_.tokenId][params_.toIndex];
    
            // update position LP state
            fromPosition.lps -= vars.lpbAmountFrom;
            toPosition.lps   += vars.lpbAmountTo;
            // update position deposit time to the from bucket deposit time
            toPosition.depositTime = vars.depositTime;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the PositionManager.moveLiquidity function, where the contract unconditionally removes the source bucket index from the EnumerableSet that tracks active positions before it knows whether any liquidity remains in that position. The function calls IPool.moveQuoteToken to transfer quote tokens from a source bucket to a destination bucket. Because moveQuoteToken respects liquidity constraints, it may return only a partial amount of the requested quote tokens, leaving a non‑zero LP balance in the source position. After the call, the code subtracts the transferred LP from the source position but has already removed the source index from the positionIndexes set. Consequently, the remaining LP becomes inaccessible: subsequent queries that rely on the index cannot locate the position, effectively freezing the funds. This issue occurs whenever the moveQuoteToken operation is constrained by insufficient quote deposits or other pool limits, i.e., any partial move scenario. It affects liquidity providers who attempt to relocate their position, causing their balances to appear unchanged or zero in the UI while the underlying assets are locked in the contract. The bug was discovered during a security audit that exercised moveLiquidity with edge‑case parameters, revealing that the position index removal logic does not account for leftover liquidity. The problem is subtle because the contract does correctly update the LP amount, so a superficial check may not notice that the position is no longer reachable. The flaw violates the protocol’s accounting assumptions that a position entry is removed only when its LP balance reaches zero. To remediate, the implementation should verify the remaining LP after subtraction and only remove the index when the balance is truly zero (or below a dust threshold), or alternatively revert the transaction if any remainder would be left, ensuring that users cannot lose access to their funds.
