---
id: 16922
severity: "High"
---

# Gas limit check is inaccurate, leading to an operator being able to fail a job intentionally

## Description

[HolographOperator.sol#L316](https://github.com/code-423n4/2022-10-holograph/blob/f8c2eae866280a1acfdc8a8352401ed031be1373/src/HolographOperator.sol#L316)  

There’s a check at line 316 that verifies that there’s enough gas left to execute the `HolographBridge.bridgeInRequest()` with the `gasLimit` set by the user, however the actual amount of gas left during the call is less than that (mainly due to the `1/64` rule, see below).  
An attacker can use that gap to fail the job while still having the `executeJob()` function complete.

## Proof of Concept

Besides using a few units of gas between the check and the actual call, there’s also a rule that only 63/64 of the remaining gas would be dedicated to an (external) function call. Since there are 2 external function calls done (`nonRevertingBridgeCall()` and the actual call to the bridge) `~2/64` of the gas isn’t sent to the bridge call and can be used after the bridge call runs out of gas.

The following PoC shows that if the amount of gas left before the call is at least 1 million then the execution can continue after the bridge call fails:

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

contract ContractTest is Test {
    event FailedOperatorJob(bytes32 jobHash);
    uint256 private _inboundMessageCounter;
    mapping(bytes32 => bool) private _failedJobs;
    constructor(){
        _inboundMessageCounter = 5;
    }
    function testGas64() public {
        this.entryPoint{gas:1000000}();
    }

    Bridge bridge = new Bridge();
    event GasLeftAfterFail(uint left);

    function entryPoint() public {

        console2.log("Gas left before call: ", gasleft());

        bytes32 hash = 0x987744358512a04274ccfb3d9649da3c116cd6b19c535e633ef8529a80cb06a0;

        try this.intermediate(){
        }catch{
            // check out how much gas is left after the call to the bridge failed
            console2.log("Gas left after failure: ", gasleft());
            // simulate operations done after failure
            _failedJobs[hash] = true;
            emit FailedOperatorJob(hash);
        }
        ++_inboundMessageCounter;
        console2.log("Gas left at end: ", gasleft());

    }

    function intermediate() public{
        bridge.bridgeCall();
    }
}

contract Bridge{
    event Done(uint gasLeft);

    uint256[] myArr;

    function bridgeCall() public {
        for(uint i =1; i <= 100; i++){
            myArr.push(i);
        }
        // this line would never be reached, we'll be out of gas beforehand
        emit Done(gasleft());
    }
}
```

Output of PoC:

```text
  Gas left before call:  999772
  Gas left after failure:  30672
  Gas left at end:  1628
```

Side note: due to some bug in forge `_inboundMessageCounter` would be considered warm even though it’s not necessarily the case. However in a real world scenario we can warm it up if the selected operator is a contract and we’er using another operator contract to execute a job in the same tx beforehand.

Reference for the `1/64` rule - [EIP-150](https://github.com/ethereum/EIPs/blob/master/EIPS/eip-150.md). Also check out [evm.codes](https://www.evm.codes/#f1?fork=grayGlacier:~:text=From%20the%20Tangerine%20Whistle%20fork%2C%20gas%20is%20capped%20at%20all%20but%20one%2064th%20\(remaining_gas%20/%2064\)%20of%20the%20remaining%20gas%20of%20the%20current%20context.%20If%20a%20call%20tries%20to%20send%20more%2C%20the%20gas%20is%20changed%20to%20match%20the%20maximum%20allowed.).

## Recommendation

Modify the required amount of gas left to gasLimit + any amount of gas spent before reaching the `call()`, then multiply it by `32/30` to mitigate the `1/64` rule (+ some margin of safety maybe).

There are some risks but would require the nested call gas limit to be pretty high (e.g. 1m used in the poc) to have enough gas (`1/64`) left afterward so that it doesn’t revert due to out-of-gas.

@gzeon - actually this is not a limitation. When the call argument passes a gaslimit which is lower than the available gas, it instantly reverts with no gas wasted. Therefore we will have `64/64` of the gas amount to work with post-revert.  
I have explained this in duplicate report [`#437`](https://github.com/code-423n4/2022-10-holograph-findings/issues/437).

You mean _higher_ than the available gas?  
I thought the same, but doing some testing and reading the Yellow Paper it turns out it wouldn’t revert just because the gas parameter is higher than the available gas.  
You can modify the PoC above to test that too.

You can check this example in Remix:

```solidity
contract Storage {
    /**
     * @dev Return value 
     * @return value of 'number'
     */
    function gas_poc() public  returns (uint256, uint256){
        uint256 left_gas = gasleft();
        address this_address = address(this);
        assembly {
            let result := call(
            /// @dev gas limit is retrieved from last 32 bytes of payload in-memory value
                left_gas,
                /// @dev destination is bridge contract
                this_address,
                /// @dev any value is passed along
                0,
                /// @dev data is retrieved from 0 index memory position
                0,
                /// @dev everything except for last 32 bytes (gas limit) is sent
                0,
                0,
                0
            )
        }
        uint256 after_left_gas = gasleft();
        return (left_gas, after_left_gas);
    }

    fallback() external {

    }
}
```

We pass a lower gas limit than what we have in the “call” opcode, which reverts.  
The function returns 

```json
{
	"0": "uint256: 3787",
	"1": "uint256: 3579"
}
```

Meaning only the gas consumed by the call opcode was deducted, not 63/64.

In your example the fallback function is actually being called, it’s just doesn’t use much gas, I’ve added an event to confirm that:

```solidity
contract Storage {
    event Cool();
    /**
     * @dev Return value 
     * @return value of 'number'
     */
    function gas_poc() public  returns (uint256, uint256){
        uint256 left_gas = gasleft();
        address this_address = address(this);
        assembly {
            let result := call(
            /// @dev gas limit is retrieved from last 32 bytes of payload in-memory value
                left_gas,
                /// @dev destination is bridge contract
                this_address,
                /// @dev any value is passed along
                0,
                /// @dev data is retrieved from 0 index memory position
                0,
                /// @dev everything except for last 32 bytes (gas limit) is sent
                0,
                0,
                0
            )
        }
        uint256 after_left_gas = gasleft();
        return (left_gas, after_left_gas);
    }

    fallback() external {
        emit Cool();
    }
}
```

Output:  
![image](https://user-images.githubusercontent.com/108216601/198561406-53968c73-3196-4f94-ad65-9ce4f2877d28.png)

A child call can never use more than 63/64 of gasleft post eip-150.

@0xA5DF - Yeah , it seems my setup when I tested this during the contest was wrong, because it instantly reverted in the CALL opcode.  
Page 37 of the Yellow book describes the GASCAP as minimum of gasLeft input and current gas counter minus costs:  
![image](https://user-images.githubusercontent.com/9900020/198568925-2f91aaed-61e2-454d-b8cf-42e9f1ce1477.png)  
Thanks for the good direct counterexample.

@gzeon - Right, we were discussing if call to child will instantly revert because `requestedGas > availableGas`, but it doesn’t.

That’s true, and the code also doesn’t forward a limited amount of gas explicitly too.

The point was that executor can always craft supplied gas to the contract, so that during the CALL opcode, gas left would be smaller than requested gas limit. If EVM behavior reverts in this check, we have deterministic failing of `bridgeIn`.

Nice find! Gas limit sent by operator could be used maliciously to ensure that job fails. This will be updated to mitigate the issue observed.

**[ACC01ADE (Holograph) resolved](https://github.com/code-423n4/2022-10-holograph-findings/issues/176#event-7817152060):**

[Feature/HOLO-604: implementing critical issue fixes](https://github.com/holographxyz/holograph-protocol/pull/84)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inaccurate verification of the remaining gas before invoking the external bridge function in the HolographOperator contract. The code checks that the current gas left is at least the user‑supplied gasLimit, but it does not take into account two important factors: the intrinsic 1/64 gas reduction imposed by EIP‑150 on every external CALL, and the small amount of gas that is consumed between the check and the actual CALL instruction. Because of this, an operator can deliberately supply a gasLimit that appears sufficient according to the naive check, yet after the EVM applies the 63/64 rule the call receives less gas than required and reverts. The outer executeJob function catches the revert and continues, marking the job as failed while still completing its own logic. An attacker acting as an operator can therefore engineer a situation where the bridgeInRequest never executes, causing the intended cross‑chain transfer or any other business logic to be skipped, yet the transaction itself succeeds from the perspective of the caller. This leads to a denial‑of‑service style effect: users who expect their assets to be bridged receive no transfer, balances remain unchanged, and protocol accounting records a failed job without the expected state change. The issue manifests only when the operator controls the gas supplied to the contract, which is the typical case for job execution in this system. It affects all participants that rely on the bridge call to complete – users, the protocol’s accounting layer, and any downstream contracts that assume the bridge execution succeeded. The flaw was uncovered during a formal security audit when test calls with a high gas stipend (around one million gas) showed that after the bridge call reverted, a non‑trivial amount of gas remained, allowing the outer function to finish and emit a failure event. The problem is subtle because the gas check looks correct on the surface; the 1/64 rule is a low‑level EVM detail that many developers overlook, and the call does not explicitly forward a limited amount of gas, making the discrepancy easy to miss. To mitigate the issue, the contract should calculate the required gas as the user‑provided limit plus any overhead incurred before the CALL, then apply a safety multiplier (for example 32/30) to cover the 63/64 reduction, or otherwise ensure that the gas supplied to the external call is explicitly checked against the post‑EIP‑150 effective gas. By doing so the contract would prevent an operator from exploiting the gas gap to force a deterministic failure of the bridge operation while still completing the surrounding job logic.
