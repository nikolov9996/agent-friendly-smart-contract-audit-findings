---
id: 23625
severity: "High"
---

# Vault rewards incorrectly scaled by cross-asset-class operator totals instead of asset class specific shares causing rewards leakage

## Description

The current vault reward distribution logic causes systematic under-distribution of rewards to vault stakers. The issue stems from using cross-asset-class operator beneficiary share totals to scale individual vault rewards, instead of using asset‑class‑specific operator rewards. This causes a leakage of rewards in scenarios where operators have asymmetric stake across different asset class IDs.

The `Rewards::_calculateAndStoreVaultShares` function incorrectly uses `operatorBeneficiariesShares[operator]` (which represents the operator's total rewards across ALL asset classes) to scale rewards for individual vaults that belong to specific asset classes. This creates an inappropriate dilution effect where vault rewards are scaled down by the operator's participation in other unrelated asset classes.

First in `_calculateOperatorShare()` when calculating the operator's total share:

```solidity
function _calculateOperatorShare(uint48 epoch, address operator) internal {
    // ... uptime calculations ...
    uint96[] memory assetClasses = l1Middleware.getAssetClassIds();
    for (uint256 i = 0; i < assetClasses.length; i++) {
        uint256 operatorStake = l1Middleware.getOperatorUsedStakeCachedPerEpoch(epoch, operator,
        assetClasses[i]);,!
        uint256 totalStake = l1Middleware.totalStakeCache(epoch, assetClasses[i]);
        uint16 assetClassShare = rewardsSharePerAssetClass[assetClasses[i]];
        uint256 shareForClass = Math.mulDiv(
            Math.mulDiv(operatorStake, BASIS_POINTS_DENOMINATOR, totalStake),
            assetClassShare, // @audit asset class share applied here
            BASIS_POINTS_DENOMINATOR
        );
        totalShare += shareForClass;
    }
    // ... rest of function
    operatorBeneficiariesShares[epoch][operator] = totalShare; //@audit this is storing cross-asset
    total,!
}
```

Again in `_calculateAndStoreVaultShares()`, `operatorBeneficiariesShares` which is a cross‑asset operator share is used to calculate vault share for a specific vault:

```solidity
function _calculateAndStoreVaultShares(uint48 epoch, address operator) internal {
    uint256 operatorShare = operatorBeneficiariesShares[epoch][operator]; // @audit already includes
    asset class weighting,!
    for (uint256 i = 0; i < vaults.length; i++) {
        address vault = vaults[i];
        uint96 vaultAssetClass = middlewareVaultManager.getVaultAssetClass(vault);
        // ... vault stake calculation ...
        uint256 vaultShare = Math.mulDiv(vaultStake, BASIS_POINTS_DENOMINATOR, operatorActiveStake);
        vaultShare = Math.mulDiv(vaultShare, rewardsSharePerAssetClass[vaultAssetClass],
        BASIS_POINTS_DENOMINATOR);,!
        vaultShare = Math.mulDiv(vaultShare, operatorShare, BASIS_POINTS_DENOMINATOR);
        //@audit Uses cross-asset operator total instead of asset‑class‑specific share
        // This scales vault rewards by operator's participation in OTHER asset classes
        // ... rest of function
    }
}
```

Net effect is, even if a specific operator contributes 100 % of the vault stake, it gets scaled by the global operator share causing a leakage in rewards for that specific asset class.

Impact: Systematic under‑rewards in every epoch where vault stakes receive less than what they should, and this excess is being reclaimed as undistributed rewards. Effectively, the actual reward distribution doesn't match intended asset class allocations.

## Proof of Concept

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;
import {Test} from "forge-std/Test.sol";
import {console2} from "forge-std/console2.sol";
import {MockAvalancheL1Middleware} from "../mocks/MockAvalancheL1Middleware.sol";
import {MockUptimeTracker} from "../mocks/MockUptimeTracker.sol";
import {MockVaultManager} from "../mocks/MockVaultManager.sol";
import {MockDelegator} from "../mocks/MockDelegator.sol";
import {MockVault} from "../mocks/MockVault.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";
import {Rewards} from "../../src/contracts/rewards/Rewards.sol";
import {IRewards} from "../../src/interfaces/rewards/IRewards.sol";
import {BaseDelegator} from "../../src/contracts/delegator/BaseDelegator.sol";
import {IVaultTokenized} from "../../src/interfaces/vault/IVaultTokenized.sol";

contract RewardsAssetShareTest is Test {
    // Contracts
    MockAvalancheL1Middleware public middleware;
    MockUptimeTracker public uptimeTracker;
    MockVaultManager public vaultManager;
    Rewards public rewards;
    ERC20Mock public rewardsToken;

    // Test addresses
    address constant ADMIN = address(0x1);
    address constant PROTOCOL_OWNER = address(0x2);
    address constant REWARDS_MANAGER = address(0x3);
    address constant REWARDS_DISTRIBUTOR = address(0x4);
    address constant OPERATOR_A = address(0x1000);
    address constant OPERATOR_B = address(uint160(0x1000 + 1));

    function setUp() public {
        // Deploy mock contracts - simplified setup for our POC
        vaultManager = new MockVaultManager();
        //Set up 2 operators
        uint256[] memory nodesPerOperator = new uint256[](2);
        nodesPerOperator[0] = 1; // Operator 0x1000 has 1 node
        nodesPerOperator[1] = 1; // Operator A has 1 node
        middleware = new MockAvalancheL1Middleware(
            30
            2,
            nodesPerOperator,
            address(0),
            address(vaultManager)
        );
        uptimeTracker = new MockUptimeTracker();
        // Deploy Rewards contract
        rewards = new Rewards();
        rewardsToken = new ERC20Mock();
        // Initialize with no fees to match our simplified example
        rewards.initialize(
            ADMIN,
            PROTOCOL_OWNER,
            payable(address(middleware)),
            address(uptimeTracker),
            0, // protocolFee = 0%
            0, // operatorFee = 0%
            0, // curatorFee = 0%
            0 // minRequiredUptime = 0
        );
        // Set up roles
        vm.prank(ADMIN);
        rewards.setRewardsManagerRole(REWARDS_MANAGER);
        vm.prank(REWARDS_MANAGER);
        rewards.setRewardsDistributorRole(REWARDS_DISTRIBUTOR);
        // Set up rewards token
        rewardsToken.mint(REWARDS_DISTRIBUTOR, 1_000_000 * 10**18);
        vm.prank(REWARDS_DISTRIBUTOR);
        rewardsToken.approve(address(rewards), 1_000_000 * 10**18);
    }

    function test_AssetShareFormula() public {
        uint48 epoch = 1;
        // Set Asset Class 1 to 50% rewards share (5000 basis points)
        vm.prank(REWARDS_MANAGER);
        rewards.setRewardsShareForAssetClass(1, 5000); // 50%
        vm.prank(REWARDS_MANAGER);
        rewards.setRewardsShareForAssetClass(2, 2000); // 20%
        vm.prank(REWARDS_MANAGER);
        rewards.setRewardsShareForAssetClass(3, 3000); // 30%
        // Set total stake in Asset Class 1 = 1000 tokens across network
        middleware.setTotalStakeCache(epoch, 1, 1000);
        middleware.setTotalStakeCache(epoch, 2, 100); // Asset Class 2: 0 tokens
        middleware.setTotalStakeCache(epoch, 3, 100); // Asset Class 3: 0 tokens
        // Set Operator A stake = 300 tokens (30% of network)
        middleware.setOperatorStake(epoch, OPERATOR_A, 1, 300);
        // Set operator A node stake (for primary asset class calculation)
        bytes32[] memory operatorNodes = middleware.getOperatorNodes(OPERATOR_A);
        middleware.setNodeStake(epoch, operatorNodes[0], 300);
        // No stake in other asset classes for Operator A
        middleware.setOperatorStake(epoch, OPERATOR_A, 2, 0);
        middleware.setOperatorStake(epoch, OPERATOR_A, 3, 0);
        bytes32[] memory operatorBNodes = middleware.getOperatorNodes(OPERATOR_B);
        middleware.setNodeStake(epoch, operatorBNodes[0], 700); // Remaining Asset Class 1 stake
        middleware.setOperatorStake(epoch, OPERATOR_B, 1, 700);
        middleware.setOperatorStake(epoch, OPERATOR_B, 2, 100);
        middleware.setOperatorStake(epoch, OPERATOR_B, 3, 100);
        // Set 100% uptime for Operator A & B
        uptimeTracker.setOperatorUptimePerEpoch(epoch, OPERATOR_A, 4 hours);
        uptimeTracker.setOperatorUptimePerEpoch(epoch, OPERATOR_B, 4 hours);
        // Create a vault for Asset Class 1 with 300 tokens staked (100% of operator's stake)
        address vault1Owner = address(0x500);
        (address vault1, address delegator1) = vaultManager.deployAndAddVault(
            address(0x123), // collateral
            vault1Owner
        );
        middleware.setAssetInAssetClass(1, vault1);
        vaultManager.setVaultAssetClass(vault1, 1);
        // Create vault for Asset Class 2
        address vault2Owner = address(0x600);
        (address vault2, address delegator2) = vaultManager.deployAndAddVault(address(0x123),
            vault2Owner);,!
        middleware.setAssetInAssetClass(2, vault2);
        vaultManager.setVaultAssetClass(vault2, 2);
        // Create vault for Asset Class 3
        address vault3Owner = address(0x700);
        (address vault3, address delegator3) = vaultManager.deployAndAddVault(
            address(0x125), // different collateral
            vault3Owner
        );
        middleware.setAssetInAssetClass(3, vault3);
        vaultManager.setVaultAssetClass(vault3, 3);
        // Set vault delegation: 300 tokens staked to Operator A
        uint256 epochTs = middleware.getEpochStartTs(epoch);
        MockDelegator(delegator1).setStake(
            middleware.L1_VALIDATOR_MANAGER(),
            1, // asset class
            OPERATOR_A,
            uint48(epochTs),
            300 // stake amount
        );
        MockDelegator(delegator1).setStake(middleware.L1_VALIDATOR_MANAGER(),
            1,
            OPERATOR_B,
            uint48(epochTs),
            700);
        MockDelegator(delegator2).setStake(
            middleware.L1_VALIDATOR_MANAGER(), 2, OPERATOR_B, uint48(epochTs), 100
        );
        MockDelegator(delegator3).setStake(
            middleware.L1_VALIDATOR_MANAGER(), 3, OPERATOR_B, uint48(epochTs), 100
        );
        // Set rewards for the epoch: 100,000 tokens
        vm.prank(REWARDS_DISTRIBUTOR);
        rewards.setRewardsAmountForEpochs(epoch, 1, address(rewardsToken), 100_000);
        // Wait 3 epochs as required by contract
        vm.warp((epoch + 3) * middleware.EPOCH_DURATION());
        // Distribute rewards
        vm.prank(REWARDS_DISTRIBUTOR);
        rewards.distributeRewards(epoch, 2);
        // Get calculated shares
        uint256 operatorABeneficiariesShare = rewards.operatorBeneficiariesShares(epoch, OPERATOR_A);
        uint256 operatorBBeneficiariesShare = rewards.operatorBeneficiariesShares(epoch, OPERATOR_B);
        uint256 vault1Share = rewards.vaultShares(epoch, vault1);
        uint256 vault2Share = rewards.vaultShares(epoch, vault2);
        uint256 vault3Share = rewards.vaultShares(epoch, vault3);
        console2.log("=== RESULTS ===");
        console2.log("operatorBeneficiariesShares[OPERATOR_A] =", operatorABeneficiariesShare, "basis
        points");,!
        console2.log("vaultShares[vault_1] =", vault1Share, "basis points");
        console2.log("operatorBeneficiariesShares[OPERATOR_B] =", operatorBBeneficiariesShare, "basis
        points");,!
        console2.log("vaultShares[vault_2] =", vault2Share, "basis points");
        console2.log("vaultShares[vault_3] =", vault3Share, "basis points");
        // Expected: 30% stake * 50% asset class = 15% = 1500 basis points
        assertEq(operatorABeneficiariesShare, 1500,
            "Operator share should be 1500 basis points (15%)");
        assertEq(vault1Share, 5000,
            "Vault share should be 5000 basis points (7.5% + 42.5)");
        assertEq(operatorBBeneficiariesShare, 8500,
            "Operator share should be 9500 basis points (85%)"); // (700/1000) 50% + (100/100) 20%
        + (100/100) 30% = 85%,!
        assertEq(vault2Share, 1700,
            "Vault share should be 1700 basis points (19%)");
        // vaultShare = (100 / 100) × 10,000 = 10,000 bp
        // vaultShare = 10,000 × 2,000 / 10,000 = 2,000 bp (vaultShare * assetClassShare / 10000)
        // vaultShare = 2,000 × 8,500 / 10,000 = 1,700 bp (vaultShare * operatorShare / 10000)
        assertEq(vault3Share, 2550,
            "Vault share should be 2550 basis points (28.5%)");
        // vaultShare = (100 / 100) × 10,000 = 10,000 bp
        // vaultShare = 10,000 × 3,000/10,000 = 3,000 bp (vaultShare * assetClassShare / 10000)
        // vaultShare = 3,000 × 8,500/10,000 = 2,550 bp (vaultShare * operatorShare / 10000)
    }
}
```

## Recommendation

Recommended Mitigation: Consider implementing a per‑asset class operator shares instead of total operator shares. The `operatorBeneficiariesShare` should be more granular and asset‑id specific to prevent this leakage. Corresponding logic in `_calculateOperatorShare` and `_calculateAndStoreVaultShares` should be adjusted specific to each assetID.

```solidity
// Add per-asset-class tracking
mapping(uint48 epoch => mapping(address operator => mapping(uint96 assetClass => uint256 share)))
public operatorBeneficiariesSharesPerAssetClass;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a systematic reward‑distribution error in the vault rewards contract. The contract calculates an operator's total beneficiary share by iterating over every asset class, weighting each class’s stake by its configured reward share, and storing the sum in a single mapping called operatorBeneficiariesShares. Later, when individual vault rewards are computed, the code retrieves this aggregated share and multiplies it with the vault’s proportional stake and the vault’s asset‑class share. Because the stored share aggregates stakes from all asset classes, a vault that belongs to a specific class is unintentionally diluted by the operator’s participation in other, unrelated classes. This root cause – using a cross‑asset‑class operator total instead of an asset‑class‑specific share – leads to under‑payment of rewards. An attacker does not need to exploit the contract; the bug is triggered automatically whenever an operator holds asymmetric stake across multiple asset classes. The impact is that vaults receive fewer rewards than the protocol’s economic design specifies, and the shortfall is retained as undistributed rewards in the contract. Users experience symptoms such as lower-than‑expected reward balances, occasional zero reward payouts, and a mismatch between the advertised asset‑class share percentages and the actual distribution. The issue occurs during the reward distribution phase of each epoch, after operator uptime and stake have been recorded, and it affects any operator with multi‑class stake, regardless of the vault size. It was discovered through audit testing that compared calculated vault shares with expected values and observed a consistent shortfall; the discrepancy was traced to the use of operatorBeneficiariesShares in the vault‑share formula. The bug can be hard to notice because the total rewards pool still decreases as expected, and only the per‑vault breakdown is incorrect, which may not be obvious without detailed accounting. To remediate, the contract should maintain a per‑asset‑class operator share mapping (e.g., operatorBeneficiariesSharesPerAssetClass[epoch][operator][assetClass]) and use that value when scaling vault rewards, thereby isolating each vault’s calculation from unrelated asset‑class participation. This change restores the intended accounting logic, ensures that rewards match the configured asset‑class percentages, and eliminates the leakage of funds into the undistributed pool.
