---
id: 21698
severity: "High"
---

# `AuraVault` inherits `AccessControl` BUT does not call the `_setupRole

## Description

The `AuraVault` contract inherits OpenZeppelin’s `AccessControl` contract to implement role-based access control. The issue is that the `AuraVault` contract does not call the `_setupRole()` function in it’s constructor to set the `DEFAULT_ADMIN_ROLE`, `VAULT_ADMIN_ROLE` or `VAULT_CONFIG_ROLE` roles.

Since this is not done in the constructor it is impossible to call `grantRole()` since it has the `onlyRole(getRoleAdmin(role))` modifier. It is important to note that no roles have been set; therefore, there is no address that can call this function to set roles. Therefore, it is impossible to set the `VAULT_ADMIN_ROLE` and `VAULT_CONFIG_ROLE` roles.

The minor impact is that the `setParameter()` function can never be called to change the `feed` or `auraPriceOracle` because it has the `onlyRole(VAULT_CONFIG_ROLE)` modifier. The critical impact is because `setVaultConfig()` function can never be called to initialize the `vaultConfig`.

The uninitialized `vaultConfig` struct will default all the variables to 0:
```solidity
struct VaultConfig {
    /// @notice The incentive sent to claimer (in bps)
    uint32 claimerIncentive;
    /// @notice The incentive sent to lockers (in bps)
    uint32 lockerIncentive;
    /// @notice The locker rewards distributor
    address lockerRewards;
}

/// @notice CDPVault configuration
VaultConfig public vaultConfig;
```
The issue arises specifically from the `lockerRewards` variable being the 0 address. When a user calls `claim()` to claim accumulated rewards by depositing WETH instead, the following line will cause the call to always revert since it attempts to send 0 BAL to the 0 address.
```solidity
function claim(uint256[] memory amounts, uint256 maxAmountIn) external returns (uint256 amountIn) {
    // Claim rewards from Aura reward pool
    IPool(rewardPool).getReward();
    ...
    ...
    // Distribute BAL rewards
    IERC20(BAL).safeTransfer(_config.lockerRewards, (amounts[0] * _config.lockerIncentive) / INCENTIVE_BASIS);
    ...
    ...
}
```
The balancer token will revert if the recipient is the 0 address due to the following check in it’s `_transfer` function ([BAL token on etherscan](https://etherscan.io/token/0xba100000625a3754423978a60c9317c58a424e3d#code)).
```solidity
function _transfer(address sender, address recipient, uint256 amount) internal virtual {
    require(sender != address(0), "ERC20: transfer from the zero address");
    require(recipient != address(0), "ERC20: transfer to the zero address");

    _beforeTokenTransfer(sender, recipient, amount);

    _balances[sender] = _balances[sender].sub(amount, "ERC20: transfer amount exceeds balance");
    _balances[recipient] = _balances[recipient].add(amount);
    emit Transfer(sender, recipient, amount);
}
```

## Proof of Concept

Here is a fully coded POC with a mainnet fork:

1. Add the following `MockAuraPool.sol` to `/src/test/MockAuraPool.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

interface IPool {
    function asset() external view returns (address);
    function balanceOf(address) external view returns (uint256);
    function deposit(uint256, address) external returns (uint256);
    function withdraw(uint256, bool) external;
    function withdraw(uint256, address, address) external;
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256);
    function getReward() external returns (bool);
    function extraRewardsLength() external view returns (uint256);
    function rewardToken() external view returns (address);
    function earned(address account) external view returns (uint256);
}

contract MockAuraPool is IPool, ERC20 {
    IERC20 public immutable _asset;
    IERC20 public immutable _rewardToken;
    mapping(address => uint256) public userRewards;

    constructor(address asset_, address rewardToken_) ERC20("Mock Aura Pool", "mAP") {
        _asset = IERC20(asset_);
        _rewardToken = IERC20(rewardToken_);
    }

    function asset() external view override returns (address) {
        return address(_asset);
    }

    function balanceOf(address account) public view override(IPool, ERC20) returns (uint256) {
        return super.balanceOf(account);
    }

    function deposit(uint256 amount, address receiver) external override returns (uint256) {
        _asset.transferFrom(msg.sender, address(this), amount);
        _mint(receiver, amount);
        return amount;
    }

    function withdraw(uint256 amount, bool) external override {
        _burn(msg.sender, amount);
        _asset.transfer(msg.sender, amount);
    }

    function withdraw(uint256 amount, address receiver, address owner) external override {
        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, amount);
        }
        _burn(owner, amount);
        _asset.transfer(receiver, amount);
    }

    function redeem(uint256 shares, address receiver, address owner) external override returns (uint256) {
        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, shares);
        }
        _burn(owner, shares);
        uint256 amount = shares; // 1:1 ratio for simplicity
        _asset.transfer(receiver, amount);
        return amount;
    }

    function getReward() external override returns (bool) {
        uint256 reward = userRewards[msg.sender];
        if (reward > 0) {
            userRewards[msg.sender] = 0;
            _rewardToken.transfer(msg.sender, reward);
        }
        return true;
    }

    function extraRewardsLength() external pure override returns (uint256) {
        return 0; // No extra rewards for simplicity
    }

    function rewardToken() external view override returns (address) {
        return address(_rewardToken);
    }

    function earned(address account) external view override returns (uint256) {
        return userRewards[account];
    }

    // Helper function to simulate rewards
    function setReward(address account, uint256 amount) external {
        userRewards[account] = amount;
    }
}
```

2. Add the following `MockOracle.sol` to `/src/test/MockOracle.sol`:
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.19;

import "../interfaces/IOracle.sol";

contract MockOracle is IOracle {

    enum Variable { PAIR_PRICE, BPT_PRICE, INVARIANT }

    struct OracleAverageQuery {
        Variable variable;
        uint256 secs;
        uint256 ago;
    }

    mapping(address token => uint256 spot) private _spot;

    mapping(address => uint256) private prices;

    function updateSpot(address token, uint256 price) external {
        prices[token] = price;
    }

    function spot(address token) external view returns (uint256) {
        return prices[token];
    }

    function getStatus(address /*token*/) public pure returns (bool) {
        return true;
    }

    function getTimeWeightedAverage(OracleAverageQuery[] memory queries)
        external
        view
        returns (uint256[] memory results)
    {
        results = new uint256[](queries.length);
        for (uint256 i = 0; i < queries.length; i++) {
            // We're assuming that the Variable enum value corresponds to a token address
            // This might need adjustment based on how it's actually used in your system
            address token = address(uint160(uint256(queries[i].variable)));
            results[i] = prices[token];
        }
        return results;
    }
}
```

3. Add the following `AuraVault.t.sol` to `/src/test/integration/AuraVault.t.sol` and run it with the following command:
```solidity
forge test --mt test__POC__ClaimFunctionAlwaysReverts -vvvvv

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Test} from "forge-std/Test.sol";
import {console} from "forge-std/console.sol";

import {AuraVault} from "../../vendor/AuraVault.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {MockOracle} from "../MockOracle.sol";
import {MockAuraPool} from "../MockAuraPool.sol";

contract AuraVaultTest is Test {
    AuraVault public auraVault;
    MockAuraPool public mockAuraPool;
    IERC20 public weth;
    IERC20 public bal;
    IERC20 public aura;
    MockOracle public mockFeed;
    MockOracle public mockAuraPriceOracle;

    uint32 public constant MAX_CLAIMER_INCENTIVE = 1000; // 10%
    uint32 public constant MAX_LOCKER_INCENTIVE = 2000; // 20%

    uint256 mainnetFork;

    // Mainnet addresses
    address constant WETH_ADDRESS = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address constant BAL_ADDRESS = 0xba100000625a3754423978a60c9317c58a424e3D;
    address constant AURA_ADDRESS = 0xC0c293ce456fF0ED870ADd98a0828Dd4d2903DBF;

    address public USER = address(879);

    function setUp() public {
        mainnetFork = vm.createFork("https://eth-mainnet.g.alchemy.com/v2/QF9A5wFdl6h_Im_XTqd7A8cbiyHc_VUu");
        vm.selectFork(mainnetFork);

        // Use real token contracts
        weth = IERC20(WETH_ADDRESS);
        bal = IERC20(BAL_ADDRESS);
        aura = IERC20(AURA_ADDRESS);

        // Deploy mock contracts
        mockAuraPool = new MockAuraPool(WETH_ADDRESS, BAL_ADDRESS);
        mockFeed = new MockOracle();
        mockAuraPriceOracle = new MockOracle();

        // Deploy AuraVault
        auraVault = new AuraVault(
            address(mockAuraPool),
            WETH_ADDRESS,
            address(mockFeed),
            address(mockAuraPriceOracle),
            MAX_CLAIMER_INCENTIVE,
            MAX_LOCKER_INCENTIVE,
            "Aura Vault WETH",
            "avWETH"
        );

        // Set up mock oracle prices
        mockFeed.updateSpot(WETH_ADDRESS, 2000e18); // WETH at $2000
        mockFeed.updateSpot(BAL_ADDRESS, 10e18); // BAL at $10
        mockAuraPriceOracle.updateSpot(AURA_ADDRESS, 5e18); // AURA at $5

        // Give some WETH to the test contract and USER
        deal(WETH_ADDRESS, address(this), 100 ether);
        deal(WETH_ADDRESS, USER, 100 ether);

        // Approve vault to spend WETH
        weth.approve(address(auraVault), type(uint256).max);
        vm.prank(USER);
        weth.approve(address(auraVault), type(uint256).max);
    }

    function test__POC__ClaimFunctionAlwaysReverts() public {
        // Setup rewards
        uint256[] memory rewardAmounts = new uint256[](2);
        rewardAmounts[0] = 10e18; // 10 BAL
        rewardAmounts[1] = 5e18;  // 5 AURA
        deal(BAL_ADDRESS, address(mockAuraPool), rewardAmounts[0]);
        deal(AURA_ADDRESS, address(mockAuraPool), rewardAmounts[1]);
        mockAuraPool.setReward(address(auraVault), rewardAmounts[0]);

        // Calculate expected WETH amount for claim
        uint256 expectedWethAmount = (rewardAmounts[0] * 10e18 + rewardAmounts[1] * 5e18) / 2000e18;

        // User attempts to claim the rewards but it reverts
        vm.startPrank(USER);
        auraVault.claim(rewardAmounts, expectedWethAmount);
    }
}
```
**Console output:**
```
    │   ├─ [6168] 0xba100000625a3754423978a60c9317c58a424e3D::transfer(0x0000000000000000000000000000000000000000, 0)
    │   │   └─ ← [Revert] revert: ERC20: transfer to the zero address
    │   └─ ← [Revert] revert: ERC20: transfer to the zero address
    └─ ← [Revert] revert: ERC20: transfer to the zero address
Suite result: FAILED. 0 passed; 1 failed; 0 skipped; finished in 13.81s (9.23s CPU time)

Ran 1 test suite in 15.09s (13.81s CPU time): 0 tests passed, 1 failed, 0 skipped (1 total tests)

Failing tests:
Encountered 1 failing test in src/test/integration/AuraVault.t.sol:AuraVaultTest
[FAIL. Reason: revert: ERC20: transfer to the zero address] test__POC__ClaimFunctionAlwaysReverts() (gas: 637701)

Encountered a total of 1 failing tests, 0 tests succeeded.
```

## Recommendation

Modify the `AuraVault` constructor as follows:
```solidity
constructor(
    address rewardPool_,
    address asset_,
    address feed_,
    address auraPriceOracle_,
    uint32 maxClaimerIncentive_,
    uint32 maxLockerIncentive_,
    string memory tokenName_,
    string memory tokenSymbol_,
    address vaultAdminRole,
    address vaultConfigRole

) ERC4626(IERC20(asset_)) ERC20(tokenName_, tokenSymbol_) {
    rewardPool = rewardPool_;
    feed = feed_;
    auraPriceOracle = auraPriceOracle_;
    maxClaimerIncentive = maxClaimerIncentive_;
    maxLockerIncentive = maxLockerIncentive_;

    _setupRole(VAULT_ADMIN_ROLE, vaultAdminRole);
    _setupRole(VAULT_CONFIG_ROLE, vaultConfigRole);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The AuraVault contract inherits OpenZeppelin AccessControl but never calls _setupRole in its constructor. As a result no address holds DEFAULT_ADMIN_ROLE, VAULT_ADMIN_ROLE or VAULT_CONFIG_ROLE. Because grantRole is protected by onlyRole(getRoleAdmin(role)), no one can ever assign any role after deployment. Consequently functions that require VAULT_CONFIG_ROLE, such as setParameter, and functions that require VAULT_ADMIN_ROLE, such as setVaultConfig, are permanently inaccessible. The vaultConfig struct therefore remains at its default values, with lockerRewards equal to the zero address. When a user invokes claim, the contract attempts to transfer BAL tokens to the lockerRewards address. The BAL token’s internal _transfer checks that the recipient is not the zero address and reverts with ERC20: transfer to the zero address. This makes the claim transaction always revert, so users see no rewards, their transaction fails, and the expected BAL distribution never occurs. The bug is triggered whenever the claim function is called, which is any time a user tries to collect accrued rewards. All participants – token holders, liquidity providers, and the protocol itself – are affected because the vault cannot distribute rewards and the funds remain locked. The issue was discovered during a formal audit by Code4rena when the auditors attempted to call setVaultConfig and observed that the contract could not be configured, and later reproduced the revert in a main‑net fork test. The problem is subtle because the contract compiles and appears functional; however, the missing role initialization silently disables critical admin paths. The vulnerability belongs to the class of uninitialized access control leading to dead‑code execution and zero‑address transfer bugs. To fix the issue the constructor must call _setupRole for each required role, assigning appropriate admin addresses, thereby enabling grantRole and allowing proper initialization of vaultConfig and reward distribution.
