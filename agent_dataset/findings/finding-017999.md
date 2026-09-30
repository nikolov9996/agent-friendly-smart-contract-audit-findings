---
id: 17999
severity: "High"
---

# Loss of user funds when completing CASH redemptions

## Description

```solidity
function completeRedemptions(
    address[] calldata redeemers,
    address[] calldata refundees,
    uint256 collateralAmountToDist,
    uint256 epochToService,
    uint256 fees
) external override updateEpoch onlyRole(MANAGER_ADMIN) {
    _checkAddressesKYC(redeemers);
    _checkAddressesKYC(refundees);
    if (epochToService >= currentEpoch) {
        revert MustServicePastEpoch();
    }
    // Calculate the total quantity of shares tokens burned w/n an epoch
    uint256 refundedAmt = _processRefund(refundees, epochToService);
    uint256 quantityBurned = redemptionInfoPerEpoch[epochToService]
        .totalBurned - refundedAmt;
    uint256 amountToDist = collateralAmountToDist - fees;
    _processRedemption(redeemers, amountToDist, quantityBurned, epochToService);
    collateral.safeTransferFrom(assetSender, feeRecipient, fees);
    emit RedemptionFeesCollected(feeRecipient, fees, epochToService);
}
```

The total refunded amount that is returned from the internal call to `_processRefund` is then used to calculate the effective amount of CASH burned (`redemptionInfoPerEpoch[epochToService].totalBurned - refundedAmt`). This resulting value is then used to calculate how much each user should receive based on how much CASH they redeemed and the total amount that was burned.

The main issue here is that the refunded amount is not updated in the `totalBurned` storage variable for the given epoch. Any subsequent call to this function won’t take into account refunds from previous calls.

## Proof of Concept

In the following test, Alice, Bob and Charlie request a redemption. The admin first calls `completeRedemptions` to process Alice’s request and refund Charlie. The admin then makes a second call to `completeRedemptions` to process Bob’s request. Even though they redeemed the same amount of CASH (each `200e18`), Alice gets `150e6` tokens while Bob is sent `~133e6`.
```solidity
contract TestAudit is BasicDeployment {
    function setUp() public {
        createDeploymentCash();

        // Grant Setter
        vm.startPrank(managerAdmin);
        cashManager.grantRole(cashManager.SETTER_ADMIN(), address(this));
        cashManager.grantRole(cashManager.SETTER_ADMIN(), managerAdmin);
        vm.stopPrank();

        // Seed address with 1000000 USDC
        vm.prank(USDC_WHALE);
        USDC.transfer(address(this), INIT_BALANCE_USDC);
    }

    function test_CashManager_completeRedemptions_BadReedem() public {
        _setupKYCStatus();

        // Seed alice and bob with 200 cash tokens
        _seed(200e18, 200e18, 50e18);

        // Have alice request to withdraw 200 cash tokens
        vm.startPrank(alice);
        tokenProxied.approve(address(cashManager), 200e18);
        cashManager.requestRedemption(200e18);
        vm.stopPrank();

        // Have bob request to withdraw 200 cash tokens
        vm.startPrank(bob);
        tokenProxied.approve(address(cashManager), 200e18);
        cashManager.requestRedemption(200e18);
        vm.stopPrank();

        // Have charlie request to withdraw his tokens
        vm.startPrank(charlie);
        tokenProxied.approve(address(cashManager), 50e18);
        cashManager.requestRedemption(50e18);
        vm.stopPrank();

        // Move forward to the next epoch
        vm.warp(block.timestamp + 1 days);
        vm.prank(managerAdmin);
        cashManager.setMintExchangeRate(2e6, 0);

        // Approve the cashMinter contract from the assetSender account
        _seedSenderWithCollateral(300e6);

        // First call, withdraw Alice and refund Charlie
        address[] memory withdrawFirstCall = new address[](1);
        withdrawFirstCall[0] = alice;
        address[] memory refundFirstCall = new address[](1);
        refundFirstCall[0] = charlie;

        vm.prank(managerAdmin);
        cashManager.completeRedemptions(
            withdrawFirstCall, // Addresses to issue collateral to
            refundFirstCall, // Addresses to refund cash
            300e6, // Total amount of money to dist incl fees
            0, // Epoch we wish to process
            0 // Fee amount to be transferred to ondo
        );

        // Alice redemption is calculated taking the refund into account
        uint256 aliceExpectedBalance = 200e18 * 300e6 / ((200e18 + 200e18 + 50e18) - 50e18);
        assertEq(USDC.balanceOf(alice), aliceExpectedBalance);
        assertEq(USDC.balanceOf(bob), 0);
        assertEq(tokenProxied.balanceOf(charlie), 50e18);

        // Second call, withdraw Bob
        address[] memory withdrawSecondCall = new address[](1);
        withdrawSecondCall[0] = bob;
        address[] memory refundSecondCall = new address[](0);

        vm.prank(managerAdmin);
        cashManager.completeRedemptions(
            withdrawSecondCall, // Addresses to issue collateral to
            refundSecondCall, // Addresses to refund cash
            300e6, // Total amount of money to dist incl fees
            0, // Epoch we wish to process
            0 // Fee amount to be transferred to ondo
        );

        // But here, Bob's redemption doesn't consider the previous refund.
        uint256 bobBadBalance = uint256(200e18 * 300e6) / (200e18 + 200e18 + 50e18);
        assertEq(USDC.balanceOf(bob), bobBadBalance);
    }

    function _setupKYCStatus() internal {
        // Add KYC addresses
        address[] memory addressesToKYC = new address[](5);
        addressesToKYC[0] = guardian;
        addressesToKYC[1] = address(cashManager);
        addressesToKYC[2] = alice;
        addressesToKYC[3] = bob;
        addressesToKYC[4] = charlie;
        registry.addKYCAddresses(kycRequirementGroup, addressesToKYC);
    }

    function _seed(
        uint256 aliceAmt,
        uint256 bobAmt,
        uint256 charlieAmt
    ) internal {
        vm.startPrank(guardian);
        tokenProxied.mint(alice, aliceAmt);
        tokenProxied.mint(bob, bobAmt);
        tokenProxied.mint(charlie, charlieAmt);
        vm.stopPrank();
    }

    function _seedSenderWithCollateral(uint256 usdcAmount) internal {
        vm.prank(USDC_WHALE);
        USDC.transfer(assetSender, usdcAmount);
        vm.prank(assetSender);
        USDC.approve(address(cashManager), usdcAmount);
    }
}
```

## Recommendation

Update the `totalBurned` amount to consider refunds resulting from the call to `_processRefund`:
```solidity
function completeRedemptions(
    address[] calldata redeemers,
    address[] calldata refundees,
    uint256 collateralAmountToDist,
    uint256 epochToService,
    uint256 fees
) external override updateEpoch onlyRole(MANAGER_ADMIN) {
    _checkAddressesKYC(redeemers);
    _checkAddressesKYC(refundees);
    if (epochToService >= currentEpoch) {
        revert MustServicePastEpoch();
    }
    // Calculate the total quantity of shares tokens burned w/n an epoch
    uint256 refundedAmt = _processRefund(refundees, epochToService);
    uint256 quantityBurned = redemptionInfoPerEpoch[epochToService]
        .totalBurned - refundedAmt;
    redemptionInfoPerEpoch[epochToService].totalBurned = quantityBurned;
    uint256 amountToDist = collateralAmountToDist - fees;
    _processRedemption(redeemers, amountToDist, quantityBurned, epochToService);
    collateral.safeTransferFrom(assetSender, feeRecipient, fees);
    emit RedemptionFeesCollected(feeRecipient, fees, epochToService);
}
```

**[ypatil12 (Ondo Finance) resolved](https://github.com/code-423n4/2023-01-ondo-findings/issues/325#issuecomment-1410627920)**

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the cash redemption workflow of the protocol. When the manager admin calls completeRedemptions, the function first determines how many CASH tokens were burned during the epoch and then subtracts any amount that was refunded to users via the internal _processRefund call. The resulting quantityBurned is used to compute each redeemer’s share of the collateral that will be transferred. However, the contract never writes the adjusted quantityBurned back to the epoch’s totalBurned storage variable. Consequently, if a refund occurs in the first call for a given epoch, the next call to completeRedemptions still sees the original totalBurned value, which includes the refunded tokens. This leads to an over‑estimation of the amount of CASH considered burned and an under‑allocation of collateral to later redeemers. The bug manifests only when multiple completeRedemptions calls are made for the same epoch and at least one of those calls processes a refund. Users who redeem after a refund receive less USDC than the proportional amount they expect, effectively losing part of their funds. The issue was uncovered during a formal audit by Code4rena, where a test scenario with three participants (Alice, Bob and Charlie) demonstrated that Alice received the correct amount after a refund to Charlie, but Bob’s subsequent redemption was short‑changed because the previous refund was not accounted for in the stored totalBurned. The problem is subtle because each individual call appears to compute the correct share; the error only becomes visible when the state is examined across calls, making it easy to miss in casual testing. The root cause is an accounting mismatch – the protocol’s invariant that totalBurned reflects the net amount of tokens actually removed from circulation is violated. To remediate the issue, the contract should update redemptionInfoPerEpoch[epoch].totalBurned with the net burned amount after subtracting refunds, ensuring that subsequent calls operate on the corrected state. This change restores the accounting guarantees, prevents inadvertent loss of user funds, and aligns the on‑chain state with the expected business logic that each user’s redemption is proportional to the net burned supply for the epoch.
