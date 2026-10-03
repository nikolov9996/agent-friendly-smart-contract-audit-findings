---
id: 25662
severity: "Crit/High"
---

# Exercise option cross chain message in the (m)TapiocaOFT will always revert in the destination, losing debited funds in the source chain

## Description



## Proof of Concept

In the `BaseTOFT`, if the packet from the received cross chain message in `lzReceive()` is of type `PT_TAP_EXERCISE`, it delegate calls to the `BaseTOFTOptionsModule`:

```solidity
function _nonblockingLzReceive(
    uint16 _srcChainId,
    bytes memory _srcAddress,
    uint64 _nonce,
    bytes memory _payload
) internal virtual override {
    uint256 packetType = _payload.toUint256(0);
    ...
    } else if (packetType == PT_TAP_EXERCISE) {
        _executeOnDestination(
            Module.Options,
            abi.encodeWithSelector(
                BaseTOFTOptionsModule.exercise.selector,
                _srcChainId,
                _srcAddress,
                _nonce,
                _payload
            ),
            _srcChainId,
            _srcAddress,
            _nonce,
            _payload
        );
    ...
```

In the `BaseTOFTOptionsModule`, the `exercise()` function is declared as:

```solidity
function exercise(
    address module,
    uint16 _srcChainId,
    bytes memory _srcAddress,
    uint64 _nonce,
    bytes memory _payload
) public {
    ...
}
```

Notice that the `address module` argument is specified in the `exercise()` function declaration, but not in the `_nonBlockingLzReceive()` call to it. This will make the message always revert because it fails when decoding the arguments to the function call, due to the extra `address module` argument.

The following POC illustrates this behaviour. The `exerciseOption()` cross chain message fails on the destination:

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

import {Test, console} from "forge-std/Test.sol";

import {TapiocaOFT} from "contracts/tOFT/TapiocaOFT.sol";
import {BaseTOFTOptionsModule} from "contracts/tOFT/modules/BaseTOFTOptionsModule.sol";

import {IYieldBoxBase} from "tapioca-periph/contracts/interfaces/IYieldBoxBase.sol";
import {ISendFrom} from "tapioca-periph/contracts/interfaces/ISendFrom.sol";
import {ICommonData} from "tapioca-periph/contracts/interfaces/ICommonData.sol";
import {ITapiocaOptionsBrokerCrossChain} from "tapioca-periph/contracts/interfaces/ITapiocaOptionsBroker.sol";

contract TapiocaOFTPOC is Test {
    address public constant LZ_ENDPOINT = 0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675;
    uint16 internal constant PT_TAP_EXERCISE = 777;

    event MessageFailed(uint16 _srcChainId, bytes _srcAddress, uint64 _nonce, bytes _payload, bytes _reason);

    function test_POC_ExerciseWrongArguments() public {
        vm.createSelectFork("https://eth.llamarpc.com");

        address optionsModule_ = address(new BaseTOFTOptionsModule(address(LZ_ENDPOINT), address(0), IYieldBoxBase(address(2)), "SomeName", "SomeSymbol", 18, block.chainid));

        TapiocaOFT tapiocaOft_ = new TapiocaOFT(
            LZ_ENDPOINT,
            address(0),
            IYieldBoxBase(address(3)),
            "SomeName",
            "SomeSymbol",
            18,
            block.chainid,
            payable(address(1)),
            payable(address(2)),
            payable(address(3)),
            payable(optionsModule_)
        );

        address user_ = makeAddr("user");
        deal(user_, 2 ether);
        vm.prank(user_);
        tapiocaOft_.wrap{value: 1 ether}(user_, user_, 1 ether);

        ITapiocaOptionsBrokerCrossChain.IExerciseOptionsData memory optionsData_;
        ITapiocaOptionsBrokerCrossChain.IExerciseLZData memory lzData_;
        ITapiocaOptionsBrokerCrossChain.IExerciseLZSendTapData memory tapSendData_;
        ICommonData.IApproval[] memory approvals_;

        optionsData_.from = user_;
        optionsData_.target = user_;
        optionsData_.paymentTokenAmount = 1 ether;
        optionsData_.oTAPTokenID = 1;
        optionsData_.paymentToken = address(0);
        optionsData_.tapAmount = 1 ether;

        lzData_.lzDstChainId = 102;
        lzData_.zroPaymentAddress = address(0);
        lzData_.extraGas = 200_000;

        tapSendData_.withdrawOnAnotherChain = false;
        tapSendData_.tapOftAddress = address(0);
        tapSendData_.lzDstChainId = 102;
        tapSendData_.amount = 0;
        tapSendData_.zroPaymentAddress = address(0);
        tapSendData_.extraGas = 0;

        tapiocaOft_.setTrustedRemoteAddress(102, abi.encodePacked(tapiocaOft_));

        vm.prank(user_);
        tapiocaOft_.exerciseOption{value: 1 ether}(
            optionsData_,
            lzData_,
            tapSendData_,
            approvals_
        );

        bytes memory lzPayload_ = abi.encode(
            PT_TAP_EXERCISE,
            optionsData_,
            tapSendData_,
            approvals_
        );

        vm.prank(LZ_ENDPOINT);
        vm.expectEmit(true, true, true, true, address(tapiocaOft_));
        emit MessageFailed(102, abi.encodePacked(tapiocaOft_, tapiocaOft_), 0, lzPayload_, vm.parseBytes("0x4e487b710000000000000000000000000000000000000000000000000000000000000041"));
        tapiocaOft_.lzReceive(102, abi.encodePacked(tapiocaOft_, tapiocaOft_), 0, lzPayload_);
    }
}
```

## Recommendation

Adding the extra module parameter when encoding the function call in `_nonBlockingLzReceive()` would be vulnerable to someone calling the `BaseTOFTOptionsModule` directly on function `exercise()` with a malicious `module` argument. It's safer to remove the `module` argument and call `exerciseInternal()` directly, which should work since it's a `public` function.

```solidity
function _nonblockingLzReceive(
    uint16 _srcChainId,
    bytes memory _srcAddress,
    uint64 _nonce,
    bytes memory _payload
) internal virtual override {
    uint256 packetType = _payload.toUint256(0);
    ...
    } else if (packetType == PT_TAP_EXERCISE) {
        _executeOnDestination(
            Module.Options,
            abi.encodeWithSelector(
                BaseTOFTOptionsModule.exercise.selector,
                address(optionsModule), // here
                _srcChainId,
                _srcAddress,
                _nonce,
                _payload
            ),
            _srcChainId,
            _srcAddress,
            _nonce,
            _payload
        );
    ...
```
