---
id: 13866
severity: "High"
---

# GradientBasedRules will not work for >=4 assets with vector lambdas

## Description

UpdateRules based on GradientBasedRule will revert/produce incorrect result when if numAssets >= 4 and lambda.length > 1. It's due to a simple mistake in updating intermediateGradientStates.

Root Cause
We have the following in QuantammGradientBasedRule.sol:156

```solidity
intermediateGradientStates[poolParameters.pool][i] = quantAMMPackTwo128( // @audit i should be replaced by locals.storageArrayIndex
    locals.intermediateGradientState[i],
    locals.secondIntermediateValue
);
unchecked {
    i += 2;
    ++locals.storageArrayIndex;
}
```

IntermediateGradientStates is a mapping to store quantum packed gradient values. If something is quantum packed, it means it will shrink roughly by half in size.

So IntermediateGradientStates[pool].length <= ceil(numAssets / 2)

In the above codebase, i is increased up to numAssets - 2. So if numAssets >= 4, intermediateGradientStates[_poolParameters.pool][i] will panic with array out of bound error (2 > 1)

Indeed, i should be replaced by locals.storageArrayIndex

PS: Interestingly, for numAssets = 5, array OOB error is not observed, because storage length is ceil(5/2) = 3 and i is increased up to 3. So there won't be OOB error, but due to the wrong usage of storage index, intermediate values will be wrong.

POC
Put the following content to QuantAMMMomentum.sol and run forge test QuantAMMMomentum --match-test testRevertWithFourAssetsAndVectorLambdas -vvv

```solidity
function testRevertWithFourAssetsAndVectorLambdas() public {
    uint256 numAssets = 4;
    // Define local variables for the parameters
    int256[][] memory parameters = new int256[][]();
    parameters[0] = new int256[]();
    parameters[0][0] = PRBMathSD59x18.fromInt(1);
    parameters[1] = new int256[]();
    parameters[1][0] = PRBMathSD59x18.fromInt(1);
    parameters[2] = new int256[]();
    parameters[2][0] = PRBMathSD59x18.fromInt(1);
    parameters[3] = new int256[]();
    parameters[3][0] = PRBMathSD59x18.fromInt(1);

    int256[] memory previousAlphas = new int256[]();
    previousAlphas[0] = PRBMathSD59x18.fromInt(1);
    previousAlphas[1] = PRBMathSD59x18.fromInt(2);
    previousAlphas[2] = PRBMathSD59x18.fromInt(3);

    int256[] memory prevMovingAverages = new int256[]();

    int256[] memory movingAverages = new int256[]();
    movingAverages[0] = 0.9e18;

    int128[] memory lambdas = new int128[]();
    lambdas[0] = int128(0.7e18);
    lambdas[1] = int128(0.7e18);
    lambdas[2] = int128(0.7e18);
    lambdas[3] = int128(0.7e18);

    int256[] memory prevWeights = new int256[]();
    prevWeights[0] = 0.2e18;
    prevWeights[1] = 0.2e18;
    prevWeights[2] = 0.2e18;
    prevWeights[3] = 0.2e18;

    int256[] memory data = new int256[]();

    int256[] memory expectedResults = new int256[]();

    /**
vm.expectRevert doesn't work for internal test functions, so just copied runInitialUpdate and inserted vm.expectRevert
     */
    mockPool.setNumberOfAssets(numAssets);
    vm.startPrank(owner);
    rule.initialisePoolRuleIntermediateValues(address(mockPool), prevMovingAverages, previousAlphas, numAssets);
    vm.expectRevert(stdError.indexOOBError);
    rule.CalculateUnguardedWeights(prevWeights, data, address(mockPool), parameters, lambdas, movingAverages);
    vm.stopPrank();
}
```
All gradient based rules (Antimomentum, ChannelFollowing, DifferenceMomentum, PowerChannel etc) won't work with >=4 assets and lambdas parameters
If numAssets is 4, 6, 8, and lambdas.length > 1, update weights will revert with index out of bound error
For numAssets 5, 7 and lambdas.length > 1, weights calculation will be incorrect because wrong index is used for intermediate value storage

## Proof of Concept

Put the following content to QuantAMMMomentum.sol and run forge test QuantAMMMomentum --match-test testRevertWithFourAssetsAndVectorLambdas -vvv

```solidity
function testRevertWithFourAssetsAndVectorLambdas() public {
    uint256 numAssets = 4;
    // Define local variables for the parameters
    int256[][] memory parameters = new int256[][]();
    parameters[0] = new int256[]();
    parameters[0][0] = PRBMathSD59x18.fromInt(1);
    parameters[1] = new int256[]();
    parameters[1][0] = PRBMathSD59x18.fromInt(1);
    parameters[2] = new int256[]();
    parameters[2][0] = PRBMathSD59x18.fromInt(1);
    parameters[3] = new int256[]();
    parameters[3][0] = PRBMathSD59x18.fromInt(1);

    int256[] memory previousAlphas = new int256[]();
    previousAlphas[0] = PRBMathSD59x18.fromInt(1);
    previousAlphas[1] = PRBMathSD59x18.fromInt(2);
    previousAlphas[2] = PRBMathSD59x18.fromInt(3);

    int256[] memory prevMovingAverages = new int256[]();

    int256[] memory movingAverages = new int256[]();
    movingAverages[0] = 0.9e18;

    int128[] memory lambdas = new int128[]();
    lambdas[0] = int128(0.7e18);
    lambdas[1] = int128(0.7e18);
    lambdas[2] = int128(0.7e18);
    lambdas[3] = int128(0.7e18);

    int256[] memory prevWeights = new int256[]();
    prevWeights[0] = 0.2e18;
    prevWeights[1] = 0.2e18;
    prevWeights[2] = 0.2e18;
    prevWeights[3] = 0.2e18;

    int256[] memory data = new int256[]();

    int256[] memory expectedResults = new int256[]();

    /**
vm.expectRevert doesn't work for internal test functions, so just copied runInitialUpdate and inserted vm.expectRevert
     */
    mockPool.setNumberOfAssets(numAssets);
    vm.startPrank(owner);
    rule.initialisePoolRuleIntermediateValues(address(mockPool), prevMovingAverages, previousAlphas, numAssets);
    vm.expectRevert(stdError.indexOOBError);
    rule.CalculateUnguardedWeights(prevWeights, data, address(mockPool), parameters, lambdas, movingAverages);
    vm.stopPrank();
}
```

## Recommendation

Apply the following patch

```solidity
diff --git a/pkg/pool-quantamm/contracts/rules/base/QuantammGradientBasedRule.sol b/pkg/pool-quantamm/contracts/rules/base/QuantammGradientBasedRule.sol
index e6bbcdc..f1f6d9f 100644
--- a/pkg/pool-quantamm/contracts/rules/base/QuantammGradientBasedRule.sol
+++ b/pkg/pool-quantamm/contracts/rules/base/QuantammGradientBasedRule.sol
@@ -153,7 +153,7 @@ abstract contract QuantAMMGradientBasedRule is ScalarRuleQuantAMMStorage {
 
                 locals.finalValues[locals.secondIndex] = locals.mulFactor.mul(locals.secondIntermediateValue);
intermediateGradientStates[poolParameters.pool][i] = quantAMMPackTwo128(
intermediateGradientStates[poolParameters.pool][locals.storageArrayIndex] = quantAMMPackTwo128(
                     locals.intermediateGradientState[i],
                     locals.secondIntermediateValue
                 );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the gradient‑based rule implementation used by the QuantAMM protocol when a pool contains four or more assets and the lambda parameter is supplied as a vector (length greater than one). The contract stores intermediate gradient values in a mapping called intermediateGradientStates, which is sized to roughly half the number of assets because the values are quantum‑packed. The update loop incorrectly writes to this mapping using the loop counter i instead of the dedicated storage index locals.storageArrayIndex. As i is incremented by two on each iteration, it quickly exceeds the maximum valid index (ceil(numAssets/2)‑1) once numAssets reaches four. When this happens the contract reverts with an out‑of‑bounds error; when the number of assets is odd (for example five) the write does not overflow but stores the value at the wrong position, corrupting the intermediate gradient state. The corrupted state propagates to the weight calculation routine, causing the pool to either revert during weight updates or to produce incorrect asset weights. From a user perspective the pool may appear to reject transactions, return zero or unexpected weight values, or silently allocate funds incorrectly, breaking the expected accounting guarantees of the protocol. The issue was uncovered during a security audit that added a targeted unit test exercising four assets with vector lambdas, which triggered the revert. It is difficult to notice in normal operation because it only manifests under the specific combination of asset count and lambda vector length, and the silent mis‑calculation for odd asset counts does not raise an exception. The root cause is a simple indexing mistake; the fix is to replace the use of i with locals.storageArrayIndex when writing to intermediateGradientStates, ensuring that values are stored within the allocated array bounds and that subsequent weight calculations use the correct intermediate data. This correction restores the intended business logic that gradient‑based rules correctly adjust asset weights based on market signals, preserving protocol safety and user funds.
