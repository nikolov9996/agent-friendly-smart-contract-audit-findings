---
id: 17217
severity: "High"
---

# `LPDA` price can underflow the price due to bad settings and potentially brick the contract

## Description

The dutch auction in the `LPDA` contract is implemented by configuring a start price and price drop per second.

A bad set of settings can cause an issue where the elapsed duration of the sale multiplied by the drop per second gets bigger than the start price and underflows the current price calculation.

```solidity
function getPrice() public view returns (uint256) {
    Sale memory temp = sale;
    (uint256 start, uint256 end) = (temp.startTime, temp.endTime);
    if (block.timestamp < start) return type(uint256).max;
    if (temp.currentId == temp.finalId) return temp.finalPrice;

    uint256 timeElapsed = end > block.timestamp ? block.timestamp - start : end - start;
    return temp.startPrice - (temp.dropPerSecond * timeElapsed);
}
```

This means that if `temp.dropPerSecond * timeElapsed > temp.startPrice` then the unsigned integer result will become negative and underflow, leading to potentially bricking the contract and an eventual loss of funds.

## Proof of Concept

In the following test, the start price is 1500 and the duration is 1 hour (3600 seconds) with a drop of 1 per second. At about ~40% of the elapsed time the price drop will start underflowing the price, reverting the calls to both `getPrice` and `buy`.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "forge-std/Test.sol";
import {FixedPriceFactory} from "src/minters/FixedPriceFactory.sol";
import {FixedPrice} from "src/minters/FixedPrice.sol";
import {OpenEditionFactory} from "src/minters/OpenEditionFactory.sol";
import {OpenEdition} from "src/minters/OpenEdition.sol";
import {LPDAFactory} from "src/minters/LPDAFactory.sol";
import {LPDA} from "src/minters/LPDA.sol";
import {Escher721} from "src/Escher721.sol";

contract AuditTest is Test {
    address deployer;
    address creator;
    address buyer;

    FixedPriceFactory fixedPriceFactory;
    OpenEditionFactory openEditionFactory;
    LPDAFactory lpdaFactory;

    function setUp() public {
        deployer = makeAddr("deployer");
        creator = makeAddr("creator");
        buyer = makeAddr("buyer");

        vm.deal(buyer, 1e18);

        vm.startPrank(deployer);

        fixedPriceFactory = new FixedPriceFactory();
        openEditionFactory = new OpenEditionFactory();
        lpdaFactory = new LPDAFactory();

        vm.stopPrank();
    }
    
    function test_LPDA_getPrice_NegativePrice() public {
        // Setup NFT and create sale
        vm.startPrank(creator);

        Escher721 nft = new Escher721();
        nft.initialize(creator, address(0), "Test NFT", "TNFT");

        // Duration is 1 hour (3600 seconds), with a start price of 1500 and a drop of 1, getPrice will revert and brick the contract at about 40% of the elapsed duration
        uint48 startId = 0;
        uint48 finalId = 1;
        uint80 startPrice = 1500;
        uint80 dropPerSecond = 1;
        uint96 startTime = uint96(block.timestamp);
        uint96 endTime = uint96(block.timestamp + 1 hours);

        LPDA.Sale memory sale = LPDA.Sale(
            startId, // uint48 currentId;
            finalId, // uint48 finalId;
            address(nft), // address edition;
            startPrice, // uint80 startPrice;
            0, // uint80 finalPrice;
            dropPerSecond, // uint80 dropPerSecond;
            endTime, // uint96 endTime;
            payable(creator), // address payable saleReceiver;
            startTime // uint96 startTime;
        );
        LPDA lpdaSale = LPDA(lpdaFactory.createLPDASale(sale));

        nft.grantRole(nft.MINTER_ROLE(), address(lpdaSale));

        vm.stopPrank();

        // simulate we are in the middle of the sale duration
        vm.warp(startTime + 0.5 hours);

        vm.startPrank(buyer);

        // getPrice will revert due to the overflow caused by the price becoming negative
        vm.expectRevert();
        lpdaSale.getPrice();

        // This will also cause the contract to be bricked, since buy needs getPrice to check that the buyer is sending the correct amount
        uint256 amount = 1;
        uint256 price = 1234;
        vm.expectRevert();
        lpdaSale.buy{value: price * amount}(amount);

        vm.stopPrank();
    }
}
```

## Recommendation

Add a validation in the `LPDAFactory.createLPDASale` function to ensure that the given duration and drop per second settings can’t underflow the price.
    
    require((sale.endTime - sale.startTime) * sale.dropPerSecond <= sale.startPrice, "MAX DROP IS GREATER THAN START PRICE");

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unsigned integer underflow in the price calculation of a Dutch‑auction style sale contract (LPDA). The contract stores a start price and a per‑second price drop, then computes the current price as startPrice minus dropPerSecond multiplied by the elapsed time. If the product of dropPerSecond and elapsed time exceeds the startPrice, the subtraction wraps around to a very large uint256 value because Solidity arithmetic on unsigned integers does not check for negative results. This situation can arise when the auction parameters are mis‑configured – for example, a long duration combined with a drop rate that is too high relative to the initial price. The underflow is not triggered at the beginning of the sale; it only appears after a certain fraction of the auction time has passed, making it easy to miss during casual testing. When the price underflows, calls to getPrice revert or return an absurdly high number, and any function that relies on getPrice (such as buy) also reverts. From a user’s perspective the buyer sees a transaction revert, receives no tokens, and may notice that the displayed price is either zero or an astronomically large value, contrary to the expectation that the price should gradually decrease. The contract becomes effectively bricked because the price function can no longer provide a sensible value, preventing further purchases and potentially locking any funds that were already sent. The issue was discovered during a formal audit when a test case simulated a sale with a start price of 1500, a duration of one hour, and a drop of one per second; after roughly 40 % of the elapsed time the price calculation underflowed and both getPrice and buy reverted. The bug belongs to the class of arithmetic underflow/overflow errors caused by unchecked arithmetic on unsigned integers and improper validation of input parameters. It violates the core business logic of a Dutch auction, which assumes that the price never becomes negative and that the price curve is monotonic decreasing to zero. To remediate, the contract should enforce a constraint that dropPerSecond multiplied by the total auction duration does not exceed the startPrice, or alternatively use safe‑math checks that cap the price at zero and prevent wrap‑around. Adding such validation at sale creation ensures that the price formula remains within the bounds of unsigned arithmetic, preserving the intended accounting behavior and preventing the contract from being bricked.
