---
id: 1741
severity: "High"
---

# L1 contract can evade aliasing, spoofing un-

## Description

A key property of the Optimism bridge is that all contract addresses are aliased.
This is to avoid a contract on L1 to be able to send messages as the same address on L2, because often these contracts will have different owners. However, using the onApprove() function, this aliasing can be evaded, giving L1 contracts this power.
When depositTransaction() is called on the Optimism Portal, we use the following check to determine whether to alias the from address:
```solidity
address from = ((_sender != tx.origin) && !_isOnApproveTrigger) ? AddressAliasHelper.applyL1ToL2Alias(_sender) : _sender;
```
As we can see, this check does not alias the address is _isOnApproveTrigger = true.
This flag is set whenever the deposit is triggered via a call to onApprove().
However, it is entirely possible for a contract to use this flow, and therefore avoid being aliased.
Internal Preconditions
None
External Preconditions
None
Attack Path
1. A contract on L1 is owned by a different user than the contract address on L2. This is typical, for example, with multisigs or safes that deployed using CREATE.
2. It wants to send a message on behalf of the L2 contract. For example, it may want to call transfer() on an ERC20 to steal their tokens.
3. It calls approveAndCall() on the Native Token on L1, including the message it wants to send on L2.
4. This message is passed along to the Optimism Portal's onApprove() function, which sets the _isOnApproveTrigger flag to true, and doesn't alias the address.
5. The result is that the L2 message comes from the unaliased L1 address, and arbitrary messages (including token transfers) can be performed on L2.
L1 contracts can send arbitrary messages from their own address on L2, allowing them to steal funds from the owners of the L2 contracts.

## Proof of Concept

The following standalone test can be used to demonstrate this vulnerability:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import { stdStorage, StdStorage, Test, console } from "forge-std/Test.sol";
import { OptimismPortal2 } from "../src/L1/OptimismPortal2.sol";
import { Constants } from "../src/libraries/Constants.sol";
import { L2NativeToken } from "../src/L1/L2NativeToken.sol";
import { ResourceMetering } from "../src/L1/ResourceMetering.sol";

contract MaliciousSafe {}
contract DummySystemConfig {
    address public nativeTokenAddress;

    constructor(address nativeToken) {
        nativeTokenAddress = nativeToken;
    }

    function resourceConfig() external view returns (ResourceMetering.ResourceConfig memory) {
        return Constants.DEFAULT_RESOURCE_CONFIG();
    }
}

contract POC is Test {
    using stdStorage for StdStorage;
    OptimismPortal2 portal;
    L2NativeToken token;

    event TransactionDeposited(address indexed from, address indexed to, uint256 indexed version, bytes opaqueData);

    function setUp() public {
        token = new L2NativeToken();
        DummySystemConfig config = new DummySystemConfig(address(token));
        portal = new OptimismPortal2(0, 0);
        stdstore.target(address(portal)).sig("systemConfig()").checked_write(address(config));
    }

    function testZach_noAlias() public {
        // we are sending from a safe, which isn't owned on L2
        address from = address(new MaliciousSafe());
        vm.startPrank(from);
        token.faucet(1);
        // let's make some transaction data
        // for example, transfer our addresses USDC on L2 to another address
        address to = makeAddr("L2USDC");
        uint value = 0;
        uint32 gasLimit = 1_000_000;
        bytes memory message = abi.encodeWithSignature("transfer(address,uint256)", address(1), 100e18);

        bytes memory onApproveData = abi.encodePacked(to, value, gasLimit, message);

        // confirm that the deposit transaction is:
        // from: from (non aliased)
        // to: L2USDC
        vm.expectEmit(true, true, false, false);
        emit TransactionDeposited(from, to, 0, bytes(""));
        // now we use approve and call to send the deposit transaction
        token.approveAndCall(address(portal), 1, onApproveData);
    }
}
```

## Recommendation

The _sender != tx.origin check is correct, even in the case that the call came via onApprove(), so the additional logic can be removed.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of the ability for a contract on L1 to bypass the address aliasing mechanism that Optimism bridge applies when sending messages to L2. The bridge normally transforms the sender address using AddressAliasHelper.applyL1ToL2Alias so that the L2 view of the sender is a distinct alias, preventing a contract that has a different owner on L2 from impersonating its L2 counterpart. The aliasing logic in OptimismPortal2's depositTransaction function checks a flag _isOnApproveTrigger and skips the alias when the flag is true. This flag is set when the deposit is initiated through the onApprove() entry point, which is reachable via the approveAndCall pattern of the L2 native token contract. Consequently, a malicious L1 contract can call approveAndCall with crafted data, cause the portal to set _isOnApproveTrigger, and have the original L1 address forwarded unchanged to L2. The exploit works whenever the attacker controls an L1 contract whose address is not the same as the L2 contract address, a common situation for multisig wallets or contracts deployed with CREATE. By sending a message that calls transfer on an ERC20 on L2, the attacker can make the L2 contract believe the call originated from the legitimate L2 address, allowing unauthorized token transfers and theft of funds. From a user perspective the symptom is that tokens disappear from the L2 contract despite no visible transaction from the expected alias; the user sees a zero balance or missing funds while the bridge reports a successful deposit. The issue was discovered during a manual audit of the bridge code, noticing that the aliasing condition excluded calls originating from onApprove. It is subtle because the normal path (direct deposit) correctly aliases, so only the less common approveAndCall flow reveals the problem, making it easy to miss in testing. The root cause is the extra conditional that overrides the aliasing check, effectively granting the L1 contract the ability to spoof its L2 identity. The recommended fix is to remove the special case and always apply the aliasing check based on _sender != tx.origin, ensuring that every L1 sender is transformed regardless of the onApprove trigger. This restores the intended security property that L1 contracts cannot impersonate L2 contracts and prevents arbitrary message injection that could lead to fund loss.
