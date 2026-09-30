---
id: 18326
severity: "High"
---

# The call to `MsgValueSimulator` with non zero `msg.value` will call to sender itself which will bypass the `onlySelf` check

## Description

First, I need to clarify, there may be more serious ways to exploit this issue. Due to the lack of time and documents, I cannot complete further exploit. The current exploit has only achieved the impact in the title. I will expand the possibility of further exploit in the poc chapter.

The call to MsgValueSimulator with non zero msg.value will call to sender itself with the msg.data. It means that if you can make a contract or a custom account call to specified address with non zero msg.value (that’s very common in withdrawal functions and smart contract wallets), you can make the contract/account call itself. And if you can also control the calldata, you can make the contract/account call its functions by itself.

It will bypass some security check with the msg.sender, or break the accounting logic of some contracts which use the msg.sender as account name.

For example the `onlySelf` modifier in the ContractDepolyer contract:

```solidity
modifier onlySelf() {
    require(msg.sender == address(this), "Callable only by self");
    _;
}
```

## Proof of Concept

The `MsgValueSimulator` use the `mimicCall` to forward the original call.

```solidity
return EfficientCall.mimicCall(gasleft(), to, _data, msg.sender, false, isSystemCall);
```

And if the `to` address is the `MsgValueSimulator` address, it will go back to the `MsgValueSimulator.fallback` function again.

The fallback function will Extract the `value` to send, isSystemCall flag and the `to` address from the extraAbi params(r3,r4,r5) in the `_getAbiParams` function. But it’s different from the first call to the `MsgValueSimulator`. The account uses `EfficientCall.rawCall` function to call the `MsgValueSimulator.fallback` in the first call. For example, code in `DefaultAccount._execute`:

```solidity
bool success = EfficientCall.rawCall(gas, to, value, data);
```

The rawCall will simulate `system_call_byref` opcode to call the `MsgValueSimulator`. And the `system_call_byref` will write the r3-r5 registers which are read as the above extraAbi params.

But the second call is sent by `EfficientCall.mimicCall`, as the return value explained in the document <https://github.com/code-423n4/2023-03-zksync/blob/main/docs/VM-specific_v1.3.0_opcodes_simulation.pdf>, `mimicCall` will mess up the registers and will use r1-r4 for standard ABI convention and r5 for the extra who _to_ mimic arg. So extraAbi params(r3-r5) read by `_getAbiParams` will be messy data. It can lead to very serious consequences, because the r3 will be used as the msg.value, and the r4 will be used as the `to` address in the final `mimicCall`. It means that the contract will send a different(greater) value to a different address, which is unexpected in the original call.

I really don’t know how to write a complex test to verify register changes in the era-compiler-tester. So to find out how to control the registers, I use the repo <https://github.com/matter-labs/zksync-era> and replace the etc/system-contracts/ codes with the lastest version in the audit, and write an integration test.

```javascript
import { TestMaster } from '../src/index';
import * as zksync from 'zksync-web3';
import { BigNumber } from 'ethers';

describe('ETH token checks', () => {
    let testMaster: TestMaster;
    let alice: zksync.Wallet;
    let bob: zksync.Wallet;

    beforeAll(() => {
        testMaster = TestMaster.getInstance(__filename);
        alice = testMaster.mainAccount();
        bob = testMaster.newEmptyAccount();
    });

    test('Can perform a transfer (legacy)', async () => {
        const LEGACY_TX_TYPE = 0;
        const value = BigNumber.from(30000);
        
        const MSG_VALUE_SYSTEM_CONTRACT = "0x0000000000000000000000000000000000008009";
        console.log(await alice.getBalance());
        console.log(await alice.provider.getBalance(MSG_VALUE_SYSTEM_CONTRACT));

        let block = await alice.provider.getBlock("latest");
        console.log("block gas limit", block.gasLimit);
        let tx_gasLimit = block.gasLimit.div(8);
        console.log("tx_gasLimit", tx_gasLimit);
        console.log("gas price", await alice.getGasPrice());

        try {
            let tx = await alice.sendTransaction({ type: LEGACY_TX_TYPE, to: MSG_VALUE_SYSTEM_CONTRACT, value , gasLimit: tx_gasLimit, data: '0x'});
            let txp = await tx.wait();
            console.log("success");
            console.log(txp["logs"]);
        } catch (err ) {
            console.log("fail");
            console.log(err);
            console.log('--------');
            console.log(err["receipt"]["logs"]);
        }
        
        console.log(await alice.getBalance());
        console.log(await alice.provider.getBalance(MSG_VALUE_SYSTEM_CONTRACT));
        console.log(await alice.getNonce());
    });

    afterAll(async () => {
        await testMaster.deinitialize();
    });
});
```

The L2EthToken Transfer event logs:

```
{
    transactionIndex: 0,
    blockNumber: 25,
    transactionHash: '0x997b6536c802620e56f8c1b54a0bd3092dfe3dde457f91ca75ec07740c82fde1',
    address: '0x000000000000000000000000000000000000800A',
    topics: [
      '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
      '0x0000000000000000000000006a8b37bcf2decff1452fccedc1452257d016b5c4',
      '0x0000000000000000000000000000000000000000000000000000000000008009'
    ],
    data: '0x0000000000000000000000000000000000000000000000000000000000007530',
    logIndex: 1,
    blockHash: '0xafb60d1285fc9ac08db01b02df01f6cbb668918d98f1b9254ed150a95957ba75'
  },
  {
    transactionIndex: 0,
    blockNumber: 25,
    transactionHash: '0x997b6536c802620e56f8c1b54a0bd3092dfe3dde457f91ca75ec07740c82fde1',
    address: '0x000000000000000000000000000000000000800A',
    topics: [
      '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
      '0x0000000000000000000000006a8b37bcf2decff1452fccedc1452257d016b5c4',
      '0x0000000000000000000000006a8b37bcf2decff1452fccedc1452257d016b5c4'
    ],
    data: '0x00000000000000000000000000000000000000000002129c0000000a00000000',
    logIndex: 2,
    blockHash: '0xafb60d1285fc9ac08db01b02df01f6cbb668918d98f1b9254ed150a95957ba75'
  }
```

There are two l2 eth token transaction in addition to gas processing. And the value sent to the `MsgValueSimulator` will stuck in the contract forever.

I found that the r4(to) is always msg.sender, the r5(mask) is always 0x1, and if the length of the calldata is 0, the r3(value) will be `0x2129c0000000a00000000`, and if the length > 0, r3(value) will be `0x215800000000a00000000 + calldata.length << 96`. So in this case, the balance of the sender should be at least 0x2129c0000000a00000000 wei to finish the whole transaction whitout reverting.

I did not find any document about the `standard ABI convention` mentioned in the VM-specific _v1.3.0\_ opcodes _simulation.pdf and the r5 is also not really the extra who\_ to_mimic arg. I didn’t make a more serious exploit due to lack of time. I’d like more documentation about register call conventions to verify the possibility of manipulating registers.

## Recommendation

Check the `to` address in the `MsgValueSimulator` contract. The `to` address must not be the `MsgValueSimulator` address.

Note: extensive discussion took place regarding this issue. Final comments are included below. For full details, please see the[original submission](https://github.com/code-423n4/2023-03-zksync-findings/issues/153).

Hey @ronnyx2017 & @Alex the Entreprenerd,
 
I managed to reproduce the issue. @ronnyx2017 is right, if Alice calls `msgValueSimulator` with `msgValueSimulator` as a recipient then:
 
  1. Alice (contract) transferred funds to the `msgValueSimulator`
  2. `msgValueSimulator` reenter itself with a changed register:
  3. value = rawFatPointer
  4. isSystemCall = isSystemCall (was set by Alice)
  5. to = Alice.address
  6. Alice reenters self contract with the same `calldata` as was sent to the `msgValueSimulator` and `value == rawFatPointer`.
  7. Alice sends `rawFatPointer` wei to herself.

Please note the `fatPointer` is the struct: 
     
     
    pub struct FatPointer {
        pub offset: u32,
        pub memory_page: u32,
        pub start: u32,
        pub length: u32,
    }

And its raw representation:
     
     
    rawFatPointer = length || start || memory_page || offset

Depending on the use case, a user could manipulate the `msg.value` of the reentrant call. However if `length > 0`, the `rawFatPointer = msg.value >= 2^96`. So if an attacker manipulates `length`, the result `msg.value` will be very large, so the attack is realistically impossible. Just as note, `2^96 wei == 79228162514 Ether == $100 trillion`.
 
So the length of the data should be 0, but manipulating other data is still possible. 
 
I see the impact of a non-unauthorized call to itself fallback function. It is indeed pretty bad, even though I don’t know any smart contract that would suffer from this in practice. 
 
All in all, I confirm the issue and appreciate that deep research, thanks a lot @ronnyx2017!

For a note here is the test that we add to our `compiler-tester` to reproduce the issue.
     
     
```solidity
pragma solidity ^0.8.0;

// The same copy of the system contracts that was on the scope.
import "./system-contracts/libraries/EfficientCall.sol";

contract Main {
    /// @dev The address of msgValueSimulator system contract.
    address constant MSG_VALUE_SIMULATOR_ADDRESS = address(0x8009);

    /// @dev Number of times that fallback function was called.
    uint256 fallbackEntrantCounter;

    function test() external payable {
        // Reset counter, after the call to msgValueSimulator it should be increased
        fallbackEntrantCounter = 0;

        require(msg.value >= 2, "msg.value should be at least 2 to ");

        // The same pattern as on `DefaultAccount`
        bool success = EfficientCall.rawCall(gasleft(), MSG_VALUE_SIMULATOR_ADDRESS, msg.value / 2, msg.data[0:0]);
        if (!success) {
            EfficientCall.propagateRevert();
        }

        require(fallbackEntrantCounter == 1, "Fallback function wasn't called");
    }
    
    fallback() external payable {
        fallbackEntrantCounter++;
     }
}
```

Last but not least, even though the impact of the issue wasn’t clear to us after triaging the report, the fix was done immediately after the end of the audit, before the launch. So this (and others) issues are not in production.
 
![Screenshot 2023-04-15 at 01 00 39](https://user-images.githubusercontent.com/41153528/232168223-dee79928-8602-4f25-b31e-ace1c301c43b.png)
 
<https://explorer.zksync.io/address/0x0000000000000000000000000000000000008009#contract>

Thank you @vladbochok for the extra detail and am glad this was already addressed.
 
I do believe self-calling opens up to a category of exploits, especially for contracts that for example use try/catch or have “unusual” behaviour around transfers.
 
I believe we can agree that the finding is unique and at least of medium severity -> Incorrect behaviour, which can conditionally lose funds.
 
We must agree that the operation also can be viewed as account hijacking, in the sense that we can impersonate the receiving contract and then have it call itself.
 
These lead me to believe that a higher severity should be appropriate.
 
Have asked for advice to other judges with the goal of clarifying if there was sufficient information in the original submission, I believe the initial POC was valid but I want to get their perspective.
 
Glad this was found and sorted.

While plenty of discussion has happened, the original finding has shown a valid POC that shows the following impact:
 
  * By performing a call with value, we can forge a call that will cause the target contract to call itself

The discussion after that helped demonstrate the report’s validity and the Sponsor has already mitigated the potential risk.
 
The ability for a specific contract to call self can be met with some skepticism in terms of its impact, however, I believe that in different scenarios, the severity would easily be raised to High.
 
For example:
 
  * Bridge contracts that call to self
  * Contract that calls to self to use try/catch
  * Vault Contracts, can be tricked into minting empty shares (no-op transfers), if the caller and the payer are the same (quirkiness of DAI)

If those contracts were in-scope and the setup demonstrated in the finding was not patched, the finding would have easily been rated as High Severity.
 
In this case, those contracts are not in-scope, so I would maintain a Medium Severity, because that’s reliant on the specific integrators using that pattern.
 
In contrast to `isSystem` which breaks an invariant on fully in-scope contracts, without the ability of causing damage, I have reason to believe that this specific vulnerability could have caused higher degrees of damage, for example:
 
  * Contracts that allow to call or delegate call
  * Vault Contracts as shown above
  * Contracts where there is no expectation that the contract can call itself (as it may mess up the balance, accounting, etc..)

Given the following considerations, I have asked myself whether this is a type of risk that would in any way be imputable to the integrator as a quirk, and at this time I cannot justify that.
 
For the logic above, because the finding has shown a way to break a very strong expectation that a contract cannot call itself unless programmed for it, considering this as `msg.sender` spoofing, although limited to `self` calls, considering the potential risks for integrators, and the breaking of expectations for EVM systems, I am raising the finding to High Severity because I believe this would have not been a risk that the Sponsor would have wanted any user nor developer to take.
 
The Sponsor has already mitigated the finding at the time of writing

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the MsgValueSimulator system contract, which forwards an incoming call using the mimicCall opcode. When a caller supplies a non‑zero msg.value and sets the destination address (the "to" parameter) to the MsgValueSimulator contract itself, the simulator forwards the call back to its own fallback function. Because the fallback is invoked with the original calldata and the msg.value is propagated through low‑level registers, the contract ends up calling itself as if it were an external account. This self‑call bypasses any checks that rely on msg.sender being equal to address(this), such as the onlySelf modifier that requires msg.sender == address(this). The root cause is the lack of validation that the "to" address cannot be the MsgValueSimulator address, combined with the mimicCall implementation that does not preserve the original register layout and therefore allows the re‑entered call to appear legitimate. An attacker can exploit this by crafting a contract or a custom account that invokes MsgValueSimulator with a non‑zero value and the simulator’s own address as the recipient, optionally controlling the calldata to trigger arbitrary functions on the target contract. The exploit results in the target contract executing its own code under the guise of an external call, which can break accounting assumptions that treat msg.sender as a unique identifier, spoof the contract’s identity, and cause unexpected value transfers. In practice the impact may be a contract’s fallback function being called without intention, funds being sent to the simulator and becoming irretrievable, or security checks like onlySelf being circumvented, leading to potential loss of funds or violation of protocol invariants. The issue manifests whenever a contract uses MsgValueSimulator for value‑simulation patterns common in withdrawal functions or smart‑contract wallets, i.e., any situation where a contract forwards a call with value through the simulator. It was discovered during a security audit when the researchers reproduced the behavior with a test contract that called the simulator and observed the fallback being entered unexpectedly. The bug is subtle because the re‑entrancy occurs at the system‑contract level and the register manipulation is not visible in high‑level Solidity code, making it hard to notice without low‑level inspection. The recommended mitigation is to add an explicit check in MsgValueSimulator that rejects calls where the destination address equals the simulator’s own address, or to redesign the forwarding logic to avoid using mimicCall for value‑bearing calls, thereby preserving the intended msg.sender semantics and preventing self‑calls. This class of vulnerability can be described as a self‑call bypass or msg.sender spoofing through unchecked destination addresses in low‑level call forwarding, which violates the business logic that a contract should not be able to invoke its own functions unless explicitly programmed to do so.
