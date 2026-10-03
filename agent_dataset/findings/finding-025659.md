---
id: 25659
severity: "Medium"
---

# Bad check in Vesting.sol::_resetVestingPlans will prevent users from adding additional liquidity in SymmVesting.sol

## Description



## Proof of Concept

Follow the guide [here](<https://hardhat.org/hardhat-runner/docs/advanced/hardhat-and-foundry>) to integrate foundry into this codebase. Then add the following test into a new file:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.8.18;

import {SymmStaking} from "../../contracts/staking/SymmStaking.sol";
import {Symmio} from "../../contracts/token/symm.sol";
import {MockERC20} from "../../contracts/mock/MockERC20.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {SymmVesting} from "../../contracts/vesting/SymmVesting.sol";
import {Test, console} from "forge-std/Test.sol";

contract TestSuite is Test {
    SymmStaking symmStaking;
    Symmio symm;
    SymmStaking implementation;
    SymmVesting symmVesting;
    SymmVesting vestingImplementation;
    address rewardToken;
    address admin;
    address lockedClaimPenaltyReceiver;
    address pool;
    address router;
    address permit2;
    address vault;
    address usdc;
    address symm_lp;

    function setUp() public {
        admin = makeAddr("admin");
        lockedClaimPenaltyReceiver = makeAddr("lockedClaimPenaltyReceiver");
        pool = 0x94Bf449AB92be226109f2Ed3CE2b297Db94bD995;
        router = 0x76578ecf9a141296Ec657847fb45B0585bCDa3a6;
        permit2 = 0x000000000022D473030F116dDEE9F6B43aC78BA3;
        vault = 0xbA1333333333a1BA1108E8412f11850A5C319bA9;
        usdc = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
        symm_lp = 0x94Bf449AB92be226109f2Ed3CE2b297Db94bD995;
        symm = Symmio(0x800822d361335b4d5F352Dac293cA4128b5B605f);
        implementation = new SymmStaking();
        vestingImplementation = new SymmVesting();

        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(address(implementation), admin, "");
        TransparentUpgradeableProxy vestingProxy =
            new TransparentUpgradeableProxy(address(vestingImplementation), admin, "");

        symmStaking = SymmStaking(address(proxy));
        symmVesting = SymmVesting(address(vestingProxy));

        vm.startPrank(admin);
        symmStaking.initialize(admin, address(symm));
        symmVesting.initialize(
            admin, lockedClaimPenaltyReceiver, pool, router, permit2, vault, address(symm), usdc, symm_lp
        );
        rewardToken = address(new MockERC20("Token", "TOK"));
        vm.stopPrank();
    }

   function testUsersWillBeUnableToProvideLiquidityAfterACertainNumberOfUnlockedTokens() public {
        //admin creates user vest with symm
        address user = makeAddr("user");
        uint256 userVestAmount = 10e18;
        uint256 totalVestedSymmAmount = 100e18;
        uint256 startTime = block.timestamp;
        uint256 endTime = block.timestamp + 10 days;
        deal(usdc, user, 1000e18);

        address[] memory users = new address[](1);
        users[0] = user;
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = userVestAmount;

        vm.startPrank(admin);
        deal(address(symm), address(symmVesting), totalVestedSymmAmount);
        symmVesting.setupVestingPlans(address(symm), startTime, endTime, users, amounts);
        vm.stopPrank();

        //user adds half their vested tokens as liquidity
        vm.startPrank(user);
        MockERC20(usdc).approve(address(symmVesting), type(uint256).max);
        symmVesting.addLiquidity(userVestAmount / 2, 0, 0);
        vm.stopPrank();

        //move time so more than half of created symm_lp vesting tokens are unlocked
        vm.warp(block.timestamp + 7 days);

        uint256 secondLiquidityAmount = symmVesting.getLockedAmountsForToken(user, address(symm));

        //second addLiquidity call will revert with "AlreadyClaimedMoreThanThis" error
        vm.startPrank(user);
        MockERC20(usdc).approve(address(symmVesting), type(uint256).max);
        vm.expectRevert();
        symmVesting.addLiquidity(secondLiquidityAmount, 0, 0);
        vm.stopPrank();
    }
}
```

## Recommendation

Remove the check:

```diff
function _resetVestingPlans(address token, address[] memory users, uint256[] memory amounts) internal {
        if (users.length != amounts.length) revert MismatchArrays();
        uint256 len = users.length;
        for (uint256 i = 0; i < len; i++) {
            address user = users[i];
            uint256 amount = amounts[i];
            _claimUnlockedToken(token, user);
            VestingPlan storage vestingPlan = vestingPlans[token][user];
-           if (amount < vestingPlan.unlockedAmount()) revert AlreadyClaimedMoreThanThis();
            uint256 oldTotal = vestingPlan.lockedAmount();
            vestingPlan.resetAmount(amount);
            totalVested[token] = totalVested[token] - oldTotal + amount;
            emit VestingPlanReset(token, user, amount);
        }
    }
```
