---
id: 25304
severity: "Low/Info"
---

# Delay can not be set to default value once set to a specific per function value

## Description



## Proof of Concept

## Vulnerability Detail

The setter for the function specific timelock is:

```solidity
function setFunctionTimelockParameters(
    address target_,
    bytes4  functionSelector_,
    uint32  delay_,
    uint32  executionWindow_
)
    external override onlySelf
{
    require(delay_           >= MIN_DELAY,            "GT:SFTP:INVALID_DELAY");
    require(executionWindow_ >= MIN_EXECUTION_WINDOW, "GT:SFTP:INVALID_EXEC_WINDOW");

    functionTimelockParameters[target_][functionSelector_] = TimelockParameters({ delay: delay_, executionWindow: executionWindow_ });

    emit FunctionTimelockSet(target_, functionSelector_, delay_, executionWindow_);
}
```

As can be seen, delay has always to be >= `MIN_DELAY`, making it impossible to set it to 0 again and allow the usage of the default timelock.

## Impact

Timelock of a function can't be set back to the default value.

## Code Snippet

[https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R118](<https://github.com/sherlock-audit/2025-09-maple-sept-8th/pull/1/files#diff-8976e5067f2102ea34580e0de5ec6762a73d214088306194672c326512646a77R118>)

## Recommendation

Allow setting the delay to 0.
