---
id: 18518
severity: "High"
---

# PositionManager’s `moveLiquidity` can set wrong deposit time and permanently freeze LP funds moved

## Description

```solidity
`moveLiquidity()` set new destination index LP entry deposit time to be equal to the source index deposit time, while destination bucket might have defaulted after that time.

This is generally not correct as source bucket bankruptcy is controlled (i.e. LP shares that are moved are healthy), while the destination bucket’s bankruptcy time, being arbitrary, can be higher than source index deposit time, and in this case the funds will become inaccessible after such a move (i.e. healthy shares will be marked as defaulted due to incorrect deposit time used).

In other words the funds are moved from healthy non-default zone to an arbitrary point, which can be either healthy or not. In the latter case this constitutes a loss for an owner as `toIndex` bucket bankruptcy time exceeding deposit time means that all other retrieval operations will be blocked.
```

## Proof of Concept

```solidity
`moveLiquidity()` sets `toPosition` deposit time to be `fromPosition.depositTime`:

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

I.e. there is no check for `params_.toIndex` bucket situation, the time is just copied.

While there is checking logic in LenderActions, which checks for `toBucket` bankruptcy and sets the time accordingly:

            vars.toBucketDepositTime = toBucketLender.depositTime;
            if (vars.toBucketBankruptcyTime >= vars.toBucketDepositTime) {
                // bucket is bankrupt and deposit was done before bankruptcy time, reset lender lp amount
                toBucketLender.lps = toBucketLP_;

                // set deposit time of the lender's to bucket as bucket's last bankruptcy timestamp + 1 so deposit won't get invalidated
                vars.toBucketDepositTime = vars.toBucketBankruptcyTime + 1;
            } else {
                toBucketLender.lps += toBucketLP_;
            }

            // set deposit time to the greater of the lender's from bucket and the target bucket
            toBucketLender.depositTime = Maths.max(vars.fromBucketDepositTime, vars.toBucketDepositTime);

This way, while bucket structure deposit time will be controlled and updated, PositionManager’s structure will have the deposit time copied over.

In the case when `positions[params_.tokenId][params_.fromIndex].depositTime` was less than `params_.toIndex` `bankruptcyTime`, this will freeze these LP funds as further attempts to use them will be blocked:

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
            ) = IPool(params_.pool).bucketInfo();

            // check that bucket hasn't gone bankrupt since memorialization
            if (vars.depositTime <= vars.bankruptcyTime) revert BucketBankrupt();

        function reedemPositions(
            RedeemPositionsParams calldata params_
        ) external override mayInteract(params_.pool, params_.tokenId) {
            EnumerableSet.UintSet storage positionIndex = positionIndexes[params_.tokenId];

            ...

            for (uint256 i = 0; i < indexesLength; ) {
                index = params_.indexes[i];

                Position memory position = positions[params_.tokenId][index];

                if (position.depositTime == 0 || position.lps == 0) revert RemovePositionFailed();

                // check that bucket didn't go bankrupt after memorialization
                if (_bucketBankruptAfterDeposit(pool, index, position.depositTime)) revert BucketBankrupt();

        function _bucketBankruptAfterDeposit(
            IPool pool_,
            uint256 index_,
            uint256 depositTime_
        ) internal view returns (bool) {
            (, , uint256 bankruptcyTime, , ) = pool_.bucketInfo(index_);
            return depositTime_ <= bankruptcyTime;
        }
```

## Recommendation

```solidity
Consider using the resulting time of the destination position, for example:

        function moveLiquidity(
            MoveLiquidityParams calldata params_
        ) external override mayInteract(params_.pool, params_.tokenId) nonReentrant {
            Position storage fromPosition = positions[params_.tokenId][params_.fromIndex];
    
            MoveLiquidityLocalVars memory vars;
            vars.depositTime = fromPosition.depositTime;
    
            ...
    
            Position storage toPosition = positions[params_.tokenId][params_.toIndex];
    
            // update position LP state
            fromPosition.lps -= vars.lpbAmountFrom;
            toPosition.lps   += vars.lpbAmountTo;
            // update position deposit time with the renewed to bucket deposit time
            (, vars.depositTime) = pool.lenderInfo(params_.toIndex, address(this));
            toPosition.depositTime = vars.depositTime;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the PositionManager.moveLiquidity function, which copies the deposit timestamp from the source liquidity bucket (fromIndex) to the destination bucket (toIndex) without verifying the bankruptcy status of the destination bucket. Deposit time is used later as a guard that prevents redemption of liquidity that was deposited before a bucket’s bankruptcy time. When a user moves healthy LP shares from a non‑default bucket into a bucket that has already passed its bankruptcy timestamp, the copied deposit time is earlier than the destination bucket’s bankruptcy time. Subsequent calls such as redeemPositions perform a check that compares the stored depositTime with the bucket’s bankruptcyTime; because the stored time is now earlier, the check fails and the contract reverts with BucketBankrupt, effectively freezing the moved LP tokens. This situation occurs only when the destination bucket’s bankruptcy time is greater than the source bucket’s deposit time, which can happen after the destination bucket has defaulted while the source bucket remains healthy. The bug was discovered during a Code4rena audit by inspecting the moveLiquidity implementation and noticing the missing validation against the target bucket’s bankruptcy state. It is hard to notice because the function appears to successfully move liquidity and the depositTime field is populated, giving the impression that the operation succeeded, yet later redemption attempts silently fail. The impact is that LP owners who use moveLiquidity may lose access to their funds, seeing their balance remain unchanged or being unable to withdraw, while the protocol’s accounting becomes inconsistent. The affected parties are liquidity providers, the protocol’s overall fund safety, and any downstream contracts that rely on correct deposit timestamps. The issue belongs to a class of time‑based state inconsistency bugs where critical accounting fields are propagated incorrectly, leading to asset‑freeze conditions. To remediate, the contract should set the destination position’s depositTime to the later of the source and destination bucket deposit times, or directly query the destination bucket’s current deposit timestamp from the pool, as demonstrated in the recommended code. This ensures that the stored depositTime always reflects a point after any possible bankruptcy, preventing the freeze and preserving the ability to redeem moved liquidity.
