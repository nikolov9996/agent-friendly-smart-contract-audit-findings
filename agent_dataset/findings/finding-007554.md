---
id: 7554
severity: "High"
---

# Subtraction in `variance()` will revert due to underflow

## Description

The function variance() in Statistics.sol subtracts the average from each number in the array but the type is uint, because of that the function will revert unless all numbers are the same

The function variance() does a subtraction by iterating on every number on the array and subtracting by the average that was previously calculated
```solidity
function variance(uint256[] memory data) internal pure returns (uint256 ans, uint256 mean) {
    mean = avg(data);
    uint256 sum = 0;
    for (uint256 i = 0; i < data.length; i++) {
        uint256 diff = data[i] - mean; 
        sum += diff * diff;
    }
    ans = sum / data.length;
}
```
The problem is that uint does not support negative values, because of that all subtractions that result in a negative amount will revert, and since it is the average of the numbers in the array, it will revert if the average is bigger than one of the numbers of the array, because of that, the only case it will not revert is if all numbers in the array are equal, and that is unlikely to happen.

This function is called in the finalizeValidation() function, which is called in the end of the validate() function, because of that, almost all calls to validate() will revert, for this reason I believe it is a high.

## Proof of Concept

Install foundry, create a file in a subfolder in the test folder, and paste this:
```solidity
// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

import { Test } from "../../lib/forge-std/src/Test.sol";
import { console } from "../../lib/forge-std/src/console.sol";

contract Statistics {

    function avg(uint256[] memory data) internal pure returns (uint256 ans) {
        uint256 sum = 0;
        for (uint256 i = 0; i < data.length; i++) {
            sum += data[i];
        }
        ans = sum / data.length;
    }

    function variance(uint256[] memory data) internal pure returns (uint256 ans, uint256 mean) {
        mean = avg(data);
        uint256 sum = 0;
        for (uint256 i = 0; i < data.length; i++) {
            uint256 diff = data[i] - mean;
            sum += diff * diff;
        }
        ans = sum / data.length;
    }

    function stddev(uint256[] memory data) internal pure returns (uint256 ans, uint256 mean) {
        (uint256 variance, uint256 mean) = variance(data);
        mean = _mean;
        ans = sqrt(_variance);
    }

    function sqrt(uint256 x) internal pure returns (uint256 y) {
        uint256 z = (x + 1) / 2;
        y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    } 
}

contract TestLib is Test, Statistics {

    function test_testAvg(uint256 number1, uint256 number2, uint256 number3, uint256 number4, uint256 number5) public {
        uint256[] memory data = new uint256[](5);
        data[0] = number1 % 1e50;
        data[1] = number2 % 1e50;
        data[2] = number3 % 1e50;
        data[3] = number4 % 1e50;
        data[4] = number5 % 1e50;
        require(number1 != number2, "test_testAvg: numbers must be different");
        uint256 ans = avg(data);
        //console.log(ans);
    }

    function test_testStddev(uint256 number1, uint256 number2, uint256 number3, uint256 number4, uint256 number5) public {
        uint256[] memory data = new uint256[](5);
        data[0] = number1 % 1e50;
        data[1] = number2 % 1e50;
        data[2] = number3 % 1e50;
        data[3] = number4 % 1e50;
        data[4] = number5 % 1e50;
        require(number1 != number2, "test_testStddev: numbers must be different");
        vm.expectRevert();
        (uint256 ans, uint256 mean) = stddev(data);
    }

    function test_testSqrt() public {
        uint256 x = 16;
        uint256 ans = sqrt(x);
        //console.log(ans);
    }

    function test_testVariance(uint256 number1, uint256 number2, uint256 number3, uint256 number4, uint256 number5) public {
        uint256[] memory data = new uint256[](5);
        data[0] = number1 % 1e50;
        data[1] = number2 % 1e50;
        data[2] = number3 % 1e50;
        data[3] = number4 % 1e50;
        data[4] = number5 % 1e50;
        require(number1 != number2, "test_testVariance: numbers must be different");
        vm.expectRevert();
        (uint256 ans, uint256 mean) = variance(data);
    }
}
```
All calls to stddev() and variance() will revert as expected. The 1e50 limit is to avoid overflows that will fail the test.

## Recommendation

Cast to int256 when calculating, the multiplication by itself will make the number always positive afterwards:
```solidity
function variance(uint256[] memory data) internal pure returns (uint256 ans, uint256 mean) {
    mean = avg(data);
    uint256 sum = 0;
    for (uint256 i = 0; i < data.length; i++) {
        int256 diff = int256(data[i]) - int256(mean); 
        sum += uint256(diff * diff);
    }
    ans = sum / data.length;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in a statistical helper routine that calculates variance on an array of unsigned integers. The routine first computes the arithmetic mean, then iterates over each element and subtracts the mean from the element using the expression `data[i] - mean`. Because both operands are of type `uint256`, the subtraction is performed in unsigned arithmetic; if any element is smaller than the calculated mean the operation underflows, producing a very large unsigned value and causing the transaction to revert due to Solidity’s built‑in overflow check (available since version 0.8). This underflow condition is triggered whenever the dataset is not perfectly uniform – that is, when at least one value differs from the average – which is the typical case for real‑world data. The function is invoked by `finalizeValidation()` at the end of a validation workflow, meaning that any call to the public `validate()` entry point will propagate the revert and abort the whole process. From a user perspective the symptom is a silent failure: a transaction that is expected to complete validation and possibly lock or release funds instead reverts, leaving the caller with no state change and often no clear error message beyond a generic revert. The impact is that the protocol’s validation mechanism becomes unusable, preventing users or validators from completing required actions, potentially freezing funds or breaking business logic that relies on successful validation. The issue was uncovered during a formal audit and reproduced with a Foundry test that deliberately supplies distinct numbers and expects a revert. It is easy to miss because the code appears mathematically correct and the subtraction looks innocuous; only when the data set contains variance does the unsigned subtraction reveal the flaw. The bug belongs to the class of arithmetic underflow/overflow errors caused by inappropriate use of unsigned types for operations that may yield negative intermediate results. To remediate, the subtraction should be performed in a signed integer domain (e.g., casting both operands to `int256` before subtraction) or the algorithm should be rewritten to avoid negative values altogether, such as by using absolute differences or by rearranging the variance formula to work with only non‑negative intermediate values. After fixing, the function will correctly compute variance for heterogeneous data sets without causing transaction reverts, restoring the intended validation flow and preserving protocol functionality.
