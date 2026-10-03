---
id: 25746
severity: "Medium"
---

# Users buying too many tickets will DoS them and the protocol if they are the winner due to OOG

## Description



## Proof of Concept

The following test costs 9 million gas, more than the block limit on Avalanche.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {WinnablesPrizeManager, LinkTokenInterface} from "contracts/WinnablesPrizeManager.sol";
import {WinnablesTicket} from "contracts/WinnablesTicket.sol";
import {IRouterClient} from "@chainlink/contracts-ccip/src/v0.8/ccip/interfaces/IRouterClient.sol";
import {Client} from "@chainlink/contracts-ccip/src/v0.8/ccip/libraries/Client.sol";

contract WinnablesPrizeManagerTest is Test {
    WinnablesPrizeManager public winnablesPrizeManager;
    WinnablesTicket public winnablesTicket;
    LinkTokenInterface public link;
    IRouterClient public router;
    address public owner;

    function setUp() public {
        vm.createSelectFork(vm.envString("ETHEREUM_RPC_URL"));
        link = LinkTokenInterface(0x514910771AF9Ca656af840dff83E8264EcF986CA);
        router = IRouterClient(0x80226fc0Ee2b096224EeAc085Bb9a8cba1146f7D);
        owner = makeAddr("owner");

        vm.prank(owner);
        winnablesPrizeManager = new WinnablesPrizeManager(address(link), address(router));

        vm.prank(owner);
        winnablesTicket = new WinnablesTicket();
    }

    function test_POC_OwnerOfDos() public {
        vm.prank(owner);
        winnablesTicket.setRole(owner, 1, true);

        vm.prank(owner);
        winnablesTicket.mint(owner, 1, 4000);

        winnablesTicket.ownerOf(1, 3999);
    }
}
```

## Impact

DoSed winner and protocol `ETH` from the raffle.

## Recommendation

Set a reasonable cap for max holdings.
