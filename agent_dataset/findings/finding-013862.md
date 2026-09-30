---
id: 13862
severity: "High"
---

# Denial of service when calculating the new weights if the rule requires previous moving averages

## Description

When the rule requires the previous moving averages in UpdateRule::CalculateNewWeights, the movingAverages[pool] array length is twice the number of assets. However, when unpacking it using the QuantAMMStorage::quantAMMUnpack128Array function, the amount of data requested is the same as the number of assets, i.e, half of the original length, causing the process to revert with an array out-of-bounds access error.

This issue causes rules like MinimumVarianceUpdateRule to permanently revert.

QuantAMMStorage::_quantAMMUnpack128Array function is used to unpack n/2 256 bit integers into n 128 bit integers (as stated in the natspec). By design, this function requires the target array to be exactly the same length as the source array before being packed, otherwise it will revert with an array out-of-bounds access error, as can be seen in the function code.

```solidity
QuantAMMStorage.sol

    function _quantAMMUnpack128Array(
        int256[] memory _sourceArray,
        uint _targetArrayLength
    ) internal pure returns (int256[] memory targetArray) {
        require(_sourceArray.length * 2 >= _targetArrayLength, "SRC!=TGT");
        targetArray = new int256[](_targetArrayLength);
        uint targetIndex;
        uint sourceArrayLengthMinusOne = _sourceArray.length - 1;
        bool divisibleByTwo = _targetArrayLength % 2 == 0;

        // @audit - _sourceArray.length is the bound of the loop, wich means that all the elements in the source array must be unpacked,
        // i.e., the function does not admit to unpack less elements than the packed.
        // @audit note * - this can be seen as a design choice or as a bug, depending on the preferences of the protocol team.
        // In this report, given the function description this is considered a design choice and the issue is in the way the function is used.
        for (uint i; i < _sourceArray.length; ) {
            targetArray[targetIndex] = _sourceArray[i] >> 128;
            unchecked {
                ++targetIndex;
            }
            if ((!divisibleByTwo && i < sourceArrayLengthMinusOne) || divisibleByTwo) {
                targetArray[targetIndex] = int256(int128(_sourceArray[i]));
            }
            unchecked {
                ++i;
                ++targetIndex;
            }
        }

        if (!divisibleByTwo) {
            targetArray[targetArrayLength - 1] = int256(int128(_sourceArray[sourceArrayLengthMinusOne]));
        }
    }
```

On the other hand, the UpdateRule::CalculateNewWeights function is used to calculate the new weights of the pool. When previous data is required, the movingAverages[pool] array length is twice the number of assets. This array is packed taking its full length (2 * numberOfAssets), however it is unpacked as if its length were the same as the number of assets in the pool. In this case, the discrepancy between the packing and unpacking length causes the process to revert because the QuantAMMStorage::quantAMMUnpack128Array function does not allow to unpack fewer elements than originally packed.

```solidity
UpdateRule.sol

    function CalculateNewWeights(
        int256[] calldata _prevWeights,
        int256[] calldata _data,
        address _pool,
        int256[][] calldata _parameters,
        uint64[] calldata _lambdaStore,
        uint64 _epsilonMax,
        uint64 _absoluteWeightGuardRail
    ) external returns (int256[] memory updatedWeights) {
        require(msg.sender == updateWeightRunner, "UNAUTH_CALC");

        QuantAMMUpdateRuleLocals memory locals;

        locals.numberOfAssets = _prevWeights.length;
        locals.nMinusOne = locals.numberOfAssets - 1;
        locals.lambda = new int128[](_lambdaStore.length);

        for (locals.i; locals.i < locals.lambda.length; ) {
            locals.lambda[locals.i] = int128(uint128(_lambdaStore[locals.i]));
            unchecked {
                ++locals.i;
            }
        }

        locals.requiresPrevAverage = requiresPrevMovingAverage() == REQPREVMAVGVAL;
        locals.intermediateMovingAverageStateLength = locals.numberOfAssets;

        if (locals.requiresPrevAverage) {
            unchecked {
                locals.intermediateMovingAverageStateLength *= 2;
            }
        }

        locals.currMovingAverage = new int256[]();
        locals.updatedMovingAverage = new int256[](locals.numberOfAssets);

        // @audit - if previous moving averages are required, length of this array is twice the number of assets
        locals.calculationMovingAverage = new int256[]();

        // @audit - In all cases locals.currMovingAverage array length is the same as the number of assets
        // furthermore, the number of assets is passed as the parameter in the function
        locals.currMovingAverage = quantAMMUnpack128Array(movingAverages[pool], locals.numberOfAssets);

        ... snip

        // @audit - if previous moving averages are required, movingAverages[_pool] array is filled by packing
        // the locals.calculationMovingAverage, which length is twice the number of assets.
        // As in all cases only locals.numberOfAssets is passed to the unpack function, the process will revert because of
        // the difference between the source and target arrays length
        if (locals.requiresPrevAverage) {
            movingAverages[pool] = quantAMMPack128Array(locals.calculationMovingAverage);
        }

        QuantAMMPoolParameters memory poolParameters;
        poolParameters.lambda = locals.lambda;
        poolParameters.movingAverage = locals.calculationMovingAverage;
        poolParameters.pool = _pool;

        //calling the function in the derived contract specific to the specific rule
        locals.unGuardedUpdatedWeights = getWeights(prevWeights, data, parameters, poolParameters);

        //Guard weights is done in the base contract so regardless of the rule the logic will always be executed
        updatedWeights = _guardQuantAMMWeights(
            locals.unGuardedUpdatedWeights,
            _prevWeights,
            int128(uint128(_epsilonMax)),
            int128(uint128(_absoluteWeightGuardRail))
        );
    }
```

Impact: High

Likelihood: Medium

## Proof of Concept

To reproduce the issue, it is possible to use the existent tests with slightly modifications. The steps to follow are: Set the UpdateRule::_requiresPrevMovingAverage function to return 1, to indicate that previous moving averages are required Take a test and make sure to call the UpdateRule::CalculateNewWeights function two times. This is important as in the first call all the initialized variables are 'adjusted' to guarantee everything works fine, but in the second time all of them are modified and become more 'realistic'.

Step 1. Set the UpdateRule::_requiresPrevMovingAverage function to return 1 It is necessary to modify the MockUpdateRule::_requiresPrevMovingAverage function.

```diff
MockUpdateRule.sol

    function _requiresPrevMovingAverage() internal pure virtual override returns (uint16) {
        return 0;
        return 1;
    }
```

\* Note. After this modification, the issue can be seen when executing the UpdateRule.t.sol::testUpdateRuleMovingAverageStorage test. It will fail because of the same root cause explained in this report.

Step 2. Take a test and make sure to call the UpdateRule::CalculateNewWeights function two times Lets take the testUpdateRuleAuthCalc test located in the test/foundry/rules/UpdateRule.t.sol file. After the call to the CalculateNewWeights function, add a second call to the same function and execute the test.

```diff
UpdateRule.t.sol

    function testUpdateRuleAuthCalc() public {
        vm.startPrank(owner);
         // Define local variables for the parameters
        
        ...snip

        //does not revert
        updateRule.CalculateNewWeights(
        prevWeights,
        data,
        address(mockPool),
        parameters,
        lambdas,
        uint64(uint256(epsilonMax)),
        uint64(0.2e18));

        // @audit - the same parameters are ok
        //does revert
        updateRule.CalculateNewWeights(
            prevWeights,
            data,
            address(mockPool),
            parameters,
            lambdas,
            uint64(uint256(epsilonMax)),
            uint64(0.2e18));

        vm.stopPrank();
    }
```

When executing the test, process will revert with the array out-of-bounds access error, causing a permanent denial of service.

## Recommendation

It is required to modify the CalculateNewWeights function to pack the correct array. As movingAverages[_pool] does not require to contain the previous values, a valid solution is the following:

```diff
UpdateRule.sol

    function CalculateNewWeights(
        int256[] calldata _prevWeights,
        int256[] calldata _data,
        address _pool,
        int256[][] calldata _parameters,
        uint64[] calldata _lambdaStore,
        uint64 _epsilonMax,
        uint64 _absoluteWeightGuardRail
    ) external returns (int256[] memory updatedWeights) {
        require(msg.sender == updateWeightRunner, "UNAUTH_CALC");

        QuantAMMUpdateRuleLocals memory locals;

        locals.numberOfAssets = _prevWeights.length;
        locals.nMinusOne = locals.numberOfAssets - 1;
        locals.lambda = new int128[](_lambdaStore.length);

        ... snip

        //because of mixing of prev and current if the numassets is odd it is makes normal code unreadable to do inline
        //this means for rules requiring prev moving average there is an addition SSTORE and local packed array
        if (locals.requiresPrevAverage) {
            movingAverages[pool] = quantAMMPack128Array(locals.calculationMovingAverage);
            movingAverages[pool] = quantAMMPack128Array(locals.updatedMovingAverage);
        }

        QuantAMMPoolParameters memory poolParameters;
        poolParameters.lambda = locals.lambda;
        poolParameters.movingAverage = locals.calculationMovingAverage;
        poolParameters.pool = _pool;

        //calling the function in the derived contract specific to the specific rule
        locals.unGuardedUpdatedWeights = getWeights(prevWeights, data, parameters, poolParameters);

        //Guard weights is done in the base contract so regardless of the rule the logic will always be executed
        updatedWeights = _guardQuantAMMWeights(
            locals.unGuardedUpdatedWeights,
            _prevWeights,
            int128(uint128(_epsilonMax)),
            int128(uint128(_absoluteWeightGuardRail))
        );
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition that occurs when a rule requires the previous moving averages during the weight‑calculation step of a QuantAMM pool. The contract stores moving averages in a packed format where each element of the original array is split into two 128‑bit integers, resulting in a source array whose length is twice the number of assets. The helper function _quantAMMUnpack128Array is designed to unpack the full packed array back into a target array of exactly the same logical size (twice the asset count). In CalculateNewWeights the code mistakenly passes the number of assets – half of the packed length – as the target length. Because the unpack routine iterates over the entire source array and writes two entries per source element, the target array runs out of bounds and the transaction reverts with an "SRC!=TGT" error. This mismatch is triggered only when the rule’s requiresPrevMovingAverage flag is true, for example in MinimumVarianceUpdateRule, so the first call may succeed but any subsequent call that needs the previous average will always revert. From a user’s perspective the pool appears to stop updating its weights; calls to the weight‑updating function return no result, balances remain unchanged and the pool may become unable to rebalance, effectively freezing the economic logic of the protocol. The issue was discovered during a manual audit that compared the packing logic with the unpacking call and noticed the length discrepancy. It is subtle because the require statement in the unpack function only checks that the source array is at least half the target length, which passes for the packed data, masking the fact that the loop writes beyond the allocated memory. The bug belongs to the class of array‑out‑of‑bounds errors caused by incorrect size assumptions when converting between packed and unpacked representations. To remediate, the CalculateNewWeights function must either pass the correct doubled length to the unpack routine or avoid unpacking the previous averages altogether, for example by packing the new moving‑average array correctly and ensuring both the source and target arrays have matching dimensions before the conversion. Properly aligning the packing and unpacking sizes eliminates the revert and restores the ability of the protocol to compute and apply new weights safely.
