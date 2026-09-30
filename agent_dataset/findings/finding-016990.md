---
id: 16990
severity: "High"
---

# Wrong implementation of function `LBPair.setFeeParameter` can break the funcionality of LBPair and make user’s tokens locked

## Description

```solidity
struct FeeParameters {
    // 144 lowest bits in slot 
    uint16 binStep;
    uint16 baseFactor;
    uint16 filterPeriod; 
    uint16 decayPeriod; 
    uint16 reductionFactor; 
    uint24 variableFeeControl;
    uint16 protocolShare;
    uint24 maxVolatilityAccumulated; 
    
    // 112 highest bits in slot 
    uint24 volatilityAccumulated;
    uint24 volatilityReference;
    uint24 indexRef;
    uint40 time; 
}
```
Function [`LBPair.setFeeParamters(bytes _packedFeeParamters)`](https://github.com/code-423n4/2022-10-traderjoe/blob/79f25d48b907f9d0379dd803fc2abc9c5f57db93/src/LBPair.sol#L788-L790) is used to set the first 8 fields which was stored in 144 lowest bits of `LBPair._feeParameter`’s slot to 144 lowest bits of `_packedFeeParameters` (The layout of `_packedFeeParameters` can be seen [here](https://github.com/code-423n4/2022-10-traderjoe/blob/79f25d48b907f9d0379dd803fc2abc9c5f57db93/src/LBFactory.sol#L572-L584)).
```solidity
/// @notice Internal function to set the fee parameters of the pair
/// @param _packedFeeParameters The packed fee parameters
function _setFeesParameters(bytes32 _packedFeeParameters) internal {
    bytes32 _feeStorageSlot;
    assembly {
        _feeStorageSlot := sload(_feeParameters.slot)
    }

    /// [#explain]  it will get 112 highest bits of feeStorageSlot,
    ///             and stores it in the 112 lowest bits of _varParameters 
    uint256 _varParameters 
        = _feeStorageSlot.decode(type(uint112).max, _OFFSET_VARIABLE_FEE_PARAMETERS/*=144*/);

    /// [#explain]  get 144 lowest bits of packedFeeParameters 
    ///             and stores it in the 144 lowest bits of _newFeeParameters  
    uint256 _newFeeParameters = _packedFeeParameters.decode(type(uint144).max, 0);

    assembly {
        // [$audit-high] wrong operation `or` here 
        //              Mitigate: or(_newFeeParameters, _varParameters << 144)    
        sstore(_feeParameters.slot, or(_newFeeParameters, _varParameters))
    }
}
```
As we can see in the implementation of `LBPair._setFeesParametes` above, it gets the 112 highest bits of `_feeStorageSlot` and stores it in the 112 lowest bits of `_varParameter`. Then it gets the 144 lowest bits of `packedFeeParameter` and stores it in the 144 lowest bits of `_newFeeParameters`.

Following the purpose of function `setFeeParameters`, the new `LBPair._feeParameters` should form as follow:
```solidity
// keep 112 highest bits remain unchanged 
// set 144 lowest bits to `_newFeeParameter`
[...112 bits...][....144 bits.....]
[_varParameters][_newFeeParameters]
```
It will make `feeParameters = _newFeeParameters | (_varParameters << 144)`. But current implementation just stores the `or` value of `_varParameters` and `_newFeeParameter` into `_feeParameters.slot`. It forgot to shift left the `_varParameters` 144 bits before executing `or` operation.

This will make the value of `binStep`, …, `maxVolatilityAccumulated` incorrect, and also remove the value (make the bit equal to 0) of `volatilityAccumulated`, …, `time`.

## Proof of Concept

Here is our test script to describe the impacts
  * <https://gist.github.com/WelToHackerLand/012e44bb85420fb53eb0bbb7f0f13769>

You can place this file into `/test` folder and run it using
```bash
forge test --match-contract High1Test -vv
```
Explanation of test script:
  1. First we create a pair with `binStep = DEFAULT_BIN_STEP = 25`
  2. We do some actions (add liquidity -> mint -> swap) to increase the value of `volatilityAccumulated` from `0` to `60000`
  3. We call function `factory.setFeeParametersOnPair` to set new fee parameters.
  4. After that the value of `volatilityAccumulated` changed to value `0` (It should still be unchanged after `factory.setFeeParametersOnPair`)
  5. We check the value of `binStep` and it changed from`25` to `60025`
     * `binStep` has that value because [line 915](https://github.com/code-423n4/2022-10-traderjoe/blob/79f25d48b907f9d0379dd803fc2abc9c5f57db93/src/LBPair.sol#L915) set `binStep = uint16(volatilityAccumulated) | binStep = 60000 | 25 = 60025`.
  6. This change of `binStep` value will break all the functionality of `LBPair` cause `binStep > Constant.BASIS_POINT_MAX = 10000` `-->` `Error: BinStepOverflows`

## Recommendation

```solidity
function _setFeesParameters(bytes32 _packedFeeParameters) internal {
    bytes32 _feeStorageSlot;
    assembly {
        _feeStorageSlot := sload(_feeParameters.slot)
    }

    uint256 _varParameters = _feeStorageSlot.decode(type(uint112).max, _OFFSET_VARIABLE_FEE_PARAMETERS);
    uint256 _newFeeParameters = _packedFeeParameters.decode(type(uint144).max, 0);

    assembly {
        sstore(_feeParameters.slot, or(_newFeeParameters, shl(144, _varParameters)))
    }
}
```

The warden has shown how, due to a missing shift, packed settings for `feeParameters` will be improperly stored, causing undefined behaviour.

The mistake can be trivially fixed and the above code offers a test case for remediation.

Because the finding impacts the protocol functionality, despite it’s perceived simplicity, I agree with High Severity as the code is not working as intended in a fundamental way.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the fee‑parameter update routine of the LBPair contract. The contract stores a packed structure of fee settings in a single 256‑bit storage slot, where the lowest 144 bits represent static parameters (such as binStep, baseFactor, filterPeriod, decayPeriod, reductionFactor, variableFeeControl, protocolShare, maxVolatilityAccumulated) and the highest 112 bits store dynamic variables (volatilityAccumulated, volatilityReference, indexRef, time). The public function setFeeParameters is supposed to replace only the static part while preserving the dynamic part. The implementation reads the current slot, extracts the dynamic 112‑bit segment, extracts the new static 144‑bit segment from the caller‑supplied bytes, and then writes the combined value back. However, the assembly write uses a plain bitwise OR between _newFeeParameters and _varParameters without first shifting the dynamic segment left by 144 bits. Consequently the dynamic fields are written into the low portion of the slot, overwriting the static fields, and the high portion of the slot is cleared to zero. The result is that values such as binStep become corrupted (e.g., binStep = volatilityAccumulated | originalBinStep) and the dynamic fields like volatilityAccumulated are reset to zero. This corruption violates the protocol’s accounting assumptions: the binStep is expected to remain within the range defined by Constant.BASIS_POINT_MAX (10 000), but after the mis‑packing it can exceed this bound, causing the contract to hit a BinStepOverflows error. When the erroneous parameters are applied, the pair’s core functions – adding liquidity, minting, swapping, and withdrawing – fail, effectively locking user tokens in the pair contract. The issue is triggered whenever an authorized entity calls factory.setFeeParametersOnPair with any new fee configuration, which is a legitimate operation in normal protocol upgrades, making the bug exploitable as a denial‑of‑service vector. The problem was discovered during a formal security audit by Code4rena; a test script demonstrated that after setting new fee parameters, the volatilityAccumulated field became zero and binStep inflated to an out‑of‑range value, causing immediate revert of subsequent operations. Because the bug manifests only as a subtle bit‑shift error, the storage layout still appears populated, and the contract does not emit explicit warnings, making it hard to notice without deep inspection of the packed representation. The recommended remediation is to shift the extracted dynamic segment left by 144 bits before OR‑combining it with the new static segment, i.e., store or(_newFeeParameters, shl(144, _varParameters)). This restores the intended separation of static and dynamic fields, prevents overflow of binStep, and ensures that fee updates no longer corrupt the pair’s state, thereby preserving user funds and protocol functionality.
